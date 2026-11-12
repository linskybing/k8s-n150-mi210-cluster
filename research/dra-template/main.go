// DRA kubelet plugin template for an accelerator "chip.example.com" (report v4, Sec. 5.3).
// It publishes one device per /dev/examplechip/<N> and injects that device node into containers through CDI.
// Replace discover() with the vendor's own enumeration (sysfs, management library); everything else is the
// standard flow of k8s.io/dynamic-resource-allocation/kubeletplugin v0.36 (Kubernetes v1.36).
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	resourceapi "k8s.io/api/resource/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/dynamic-resource-allocation/kubeletplugin"
	"k8s.io/dynamic-resource-allocation/resourceslice"
	"k8s.io/klog/v2"
	"k8s.io/utils/ptr"
)

const (
	driverName = "chip.example.com"      // DeviceClass selector: device.driver == 'chip.example.com'
	cdiKind    = "k8s.chip.example.com/chip" // CDI IDs are "<cdiKind>=<name>"
	cdiDir     = "/var/run/cdi"          // containerd and CRI-O read CDI specs from here
)

type chip struct {
	name, devNode, model, pciAddress string
	memoryBytes                      int64
}

// discover lists the chips on this node. Template only: the vendor reads model, PCI address and memory from its driver.
func discover() ([]chip, error) {
	nodes, err := filepath.Glob("/dev/examplechip/[0-9]*")
	if err != nil {
		return nil, err
	}
	var chips []chip
	for i, n := range nodes {
		chips = append(chips, chip{name: fmt.Sprintf("chip-%d", i), devNode: n, model: "example-x1",
			pciAddress: "0000:00:00.0", memoryBytes: 16 << 30})
	}
	return chips, nil
}

type driver struct{ chips map[string]chip }

// PrepareResourceClaims runs when kubelet starts a Pod that holds an allocated claim (gRPC NodePrepareResources):
// write a CDI spec per allocated device and return its CDI ID; the container runtime then adds the device node.
func (d *driver) PrepareResourceClaims(ctx context.Context, claims []*resourceapi.ResourceClaim) (map[types.UID]kubeletplugin.PrepareResult, error) {
	out := map[types.UID]kubeletplugin.PrepareResult{}
	for _, claim := range claims {
		var res kubeletplugin.PrepareResult
		for _, r := range claim.Status.Allocation.Devices.Results {
			if r.Driver != driverName {
				continue
			}
			c, ok := d.chips[r.Device]
			if !ok {
				res.Err = fmt.Errorf("device %s not on this node", r.Device)
				break
			}
			name := fmt.Sprintf("%s-%s", claim.UID, r.Device)
			if err := writeCDISpec(name, c.devNode); err != nil {
				res.Err = err
				break
			}
			res.Devices = append(res.Devices, kubeletplugin.Device{Requests: []string{r.Request}, PoolName: r.Pool,
				DeviceName: r.Device, CDIDeviceIDs: []string{cdiKind + "=" + name}})
		}
		out[claim.UID] = res
	}
	return out, nil
}

// UnprepareResourceClaims runs after the Pod is gone (gRPC NodeUnprepareResources): remove the claim's CDI specs.
func (d *driver) UnprepareResourceClaims(ctx context.Context, claims []kubeletplugin.NamespacedObject) (map[types.UID]error, error) {
	out := map[types.UID]error{}
	for _, claim := range claims {
		files, err := filepath.Glob(filepath.Join(cdiDir, fmt.Sprintf("chip-%s-*.json", claim.UID)))
		for _, f := range files {
			if e := os.Remove(f); e != nil && err == nil {
				err = e
			}
		}
		out[claim.UID] = err
	}
	return out, nil
}

func (d *driver) HandleError(ctx context.Context, err error, msg string) {
	klog.FromContext(ctx).Error(err, msg)
}

// writeCDISpec writes a Container Device Interface spec that maps one CDI device to one host device node.
func writeCDISpec(name, devNode string) error {
	spec := map[string]any{
		"cdiVersion": "0.6.0",
		"kind":       cdiKind,
		"devices": []any{map[string]any{"name": name,
			"containerEdits": map[string]any{"deviceNodes": []any{map[string]any{"path": devNode}}}}},
	}
	b, err := json.Marshal(spec)
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(cdiDir, "chip-"+name+".json"), b, 0o644)
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	node := os.Getenv("NODE_NAME") // from the DaemonSet (fieldRef spec.nodeName)

	chips, err := discover()
	if err != nil {
		klog.Fatal(err)
	}
	cfg, err := rest.InClusterConfig()
	if err != nil {
		klog.Fatal(err)
	}
	d := &driver{chips: map[string]chip{}}
	var devices []resourceapi.Device
	for _, c := range chips {
		d.chips[c.name] = c
		devices = append(devices, resourceapi.Device{
			Name: c.name,
			Attributes: map[resourceapi.QualifiedName]resourceapi.DeviceAttribute{ // what users filter on with CEL
				"model":      {StringValue: ptr.To(c.model)},
				"pciAddress": {StringValue: ptr.To(c.pciAddress)},
			},
			Capacity: map[resourceapi.QualifiedName]resourceapi.DeviceCapacity{
				"memory": {Value: *resource.NewQuantity(c.memoryBytes, resource.BinarySI)},
			},
		})
	}

	// Registers with kubelet (plugins_registry) and serves the DRA gRPC API under /var/lib/kubelet/plugins/<driverName>.
	helper, err := kubeletplugin.Start(ctx, d,
		kubeletplugin.KubeClient(kubernetes.NewForConfigOrDie(cfg)),
		kubeletplugin.NodeName(node),
		kubeletplugin.DriverName(driverName))
	if err != nil {
		klog.Fatal(err)
	}
	defer helper.Stop()

	// One pool per node; the helper creates and updates the node's ResourceSlice.
	if err := helper.PublishResources(ctx, resourceslice.DriverResources{
		Pools: map[string]resourceslice.Pool{node: {Slices: []resourceslice.Slice{{Devices: devices}}}},
	}); err != nil {
		klog.Fatal(err)
	}
	<-ctx.Done()
}
