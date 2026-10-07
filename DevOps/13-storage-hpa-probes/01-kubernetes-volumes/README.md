# 01 — Kubernetes Volumes

Session 13, Task 1. My notes on **emptyDir, hostPath, PersistentVolume,
PersistentVolumeClaim, StorageClass and dynamic provisioning**, each with a
practical example that I ran.

The hands-on transcripts these examples come from are in the
[main session README](../README.md#task-1--ephemeral-volumes) (Tasks 1–3, run on the
three-node `devops-hw` kind cluster) and in
[`../evidence/`](../evidence/) (`s13-volumes.txt`, `s13-static.txt`,
`s13-dynamic.txt`). The StorageClass and provisioner details in sections 5–6 were
captured again on the single-node `hw-legacy` cluster, together with the PVC of
the [mini project](../mini-project/README.md):
[`../evidence/s13-storageclass-hw-legacy.txt`](../evidence/s13-storageclass-hw-legacy.txt).

---

## Why volumes exist

A container's filesystem lasts only as long as the container. When the
container restarts, whatever it wrote is gone. Volumes fix that at three
levels:

| Lifetime of the data | Volume type | Example use |
|---|---|---|
| as long as the **pod** | `emptyDir` | scratch space, cache, sharing files between containers |
| as long as the **node** | `hostPath` | node agents reading `/var/log`, `/proc` |
| independent of pod and node | **PV + PVC** (often via a **StorageClass**) | databases, uploads, anything that matters |

A volume is declared once under `spec.volumes` and mounted into containers with
`volumeMounts`. Two containers mounting the same volume see the same files.

---

## 1. emptyDir

**What it is:** an empty directory created when the pod is scheduled onto a
node, and deleted when the pod leaves that node. Every container in the pod can
mount it. It survives a **container** restart but not a **pod** deletion.
`emptyDir: {medium: Memory}` makes it a RAM-backed tmpfs.

```yaml
# ../manifests/volumes/emptydir.yaml (excerpt)
containers:
  - name: writer
    command: ["sh", "-c", "i=0; while true; do i=$((i+1)); echo \"line $i\" >> /shared/log.txt; sleep 3; done"]
    volumeMounts: [{ name: scratch, mountPath: /shared }]
  - name: reader
    volumeMounts: [{ name: scratch, mountPath: /shared }]
volumes:
  - name: scratch
    emptyDir: {}
```

**Practical result:**

```console
$ kubectl exec emptydir-demo -c reader -- cat /shared/log.txt
line 1
line 2
line 3
line 4
line 5

$ kubectl delete pod emptydir-demo && kubectl apply -f manifests/volumes/emptydir.yaml
$ kubectl exec emptydir-demo -c reader -- cat /shared/log.txt
line 1
line 2
```

The reader saw the writer's lines, because it is one volume mounted twice.
After the pod was recreated, the count started again at 1 and the old lines
were gone for good.

**Use it for** caches, temporary files, and handing data from an init container
or a sidecar to the main container. **Never** use it for data you need to keep.

---

## 2. hostPath

**What it is:** mounts a real directory from the **node's** filesystem into the
pod.

```yaml
# ../manifests/volumes/hostpath.yaml (excerpt)
spec:
  nodeName: devops-hw-worker        # pinned: the data exists on one node only
  volumes:
    - name: host-data
      hostPath:
        path: /tmp/k8s-hostpath-demo
        type: DirectoryOrCreate
```

**Practical result:** a file written inside the pod could be read straight
from the node container, outside Kubernetes. A file written on the node showed
up inside the pod:

```console
$ kubectl exec hostpath-demo -- sh -c 'echo "written from inside the pod" > /host-data/from-pod.txt'
$ docker exec devops-hw-worker cat /tmp/k8s-hostpath-demo/from-pod.txt
written from inside the pod

$ docker exec devops-hw-worker sh -c 'echo "written from the node" > /tmp/k8s-hostpath-demo/from-node.txt'
$ kubectl exec hostpath-demo -- cat /host-data/from-node.txt
written from the node
```

**What I learned:** hostPath ties the pod to one node. If the pod is
rescheduled to another node it sees an empty directory. It is also a security
risk, because a pod that mounts `/` or the container runtime socket controls the
node. It is meant for node-level agents (log shippers, monitoring) and not for
application data. Many clusters block it with Pod Security admission.

---

## 3. PersistentVolume (PV)

**What it is:** a piece of storage in the cluster, represented as a
cluster-scoped API object. It records the capacity, access modes (`RWO`
ReadWriteOnce, `ROX` ReadOnlyMany, `RWX` ReadWriteMany, `RWOP` ReadWriteOncePod),
the **reclaim policy**, and the backend (NFS, a cloud disk, local path,
hostPath for labs). An administrator creates it in advance (static
provisioning), or a provisioner creates it on demand (section 6).

```yaml
# ../manifests/persistent/01-static-pv.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: manual-pv
spec:
  capacity:
    storage: 1Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain   # keep the data after the PVC is deleted
  storageClassName: manual
  hostPath:
    path: /tmp/k8s-manual-pv
    type: DirectoryOrCreate
```

```console
$ kubectl get pv manual-pv
NAME        CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   ...
manual-pv   1Gi        RWO            Retain           Available           manual
```

A PV goes through these phases: `Available` → `Bound` → `Released` (after its
claim is deleted) → reused or deleted, depending on the reclaim policy.
**Retain** keeps the data for manual recovery. **Delete** removes the backing
storage along with the PV.

---

## 4. PersistentVolumeClaim (PVC)

**What it is:** a namespaced **request** for storage: "I need 500Mi, RWO, of
class X". Pods never refer to a PV directly. They refer to a claim, so the app
manifest stays the same whatever storage backend sits underneath.

```yaml
# ../manifests/persistent/02-static-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: manual-pvc
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: manual
  resources:
    requests:
      storage: 500Mi
---
# used by a pod as:
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: manual-pvc
```

**Practical results:**

```console
$ kubectl get pvc manual-pvc -o jsonpath='requested={.spec.resources.requests.storage} bound={.status.capacity.storage} volume={.spec.volumeName}'
requested=500Mi bound=1Gi volume=manual-pv

$ kubectl exec static-storage-pod -- cat /data/important.txt
persistent data written at 09:24:58
$ kubectl delete pod static-storage-pod && kubectl apply -f manifests/persistent/03-static-pod.yaml
$ kubectl exec static-storage-pod -- cat /data/important.txt
persistent data written at 09:24:58
```

- Binding means "at least this big, with compatible modes and class", not an
  exact match. The 500Mi claim took the whole 1Gi PV, and the extra 512Mi
  cannot be used by any other claim.
- The data survived the pod being deleted and recreated. This is the same test
  that lost all its data with `emptyDir`.
- The mini project repeats this with a Deployment: a file written by one
  replica was still there in a replacement pod created after a delete
  ([mini project, Task 1](../mini-project/README.md)).

---

## 5. StorageClass

**What it is:** a template for creating volumes on demand. It names a
**provisioner** (the driver that creates the storage), its parameters, the
reclaim policy for the PVs it creates, and the **volume binding mode**. A claim
picks a class with `storageClassName`. If it leaves that field out, it gets
the class marked as default.

Captured on the `hw-legacy` kind cluster (YAML trimmed of metadata noise):

```console
$ kubectl get storageclass
NAME                 PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
standard (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  24m

$ kubectl get storageclass standard -o yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
  name: standard
provisioner: rancher.io/local-path
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

| Field | Meaning here |
|---|---|
| `provisioner: rancher.io/local-path` | kind's built-in provisioner. On a cloud this would be `ebs.csi.aws.com`, `pd.csi.storage.gke.io`, `disk.csi.azure.com` |
| `reclaimPolicy: Delete` | deleting the PVC deletes the PV **and the data** |
| `volumeBindingMode: WaitForFirstConsumer` | don't create the volume until a pod using it is scheduled, so the volume ends up where the pod runs (same node or zone) |
| `is-default-class: "true"` | claims that don't set `storageClassName` get this class |

---

## 6. Dynamic provisioning

**What it is:** nobody creates PVs by hand. A claim names a StorageClass, the
provisioner sees the claim, creates the real storage plus a PV of exactly the
requested size, and binds them.

```yaml
# ../manifests/persistent/04-dynamic-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard
  resources:
    requests:
      storage: 1Gi
```

**Practical result:** the claim stayed `Pending` (correctly) until a pod used
it, then the provisioner did the rest:

```console
$ kubectl get pvc dynamic-pvc
NAME          STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   ...
dynamic-pvc   Pending                                      standard

$ kubectl describe pvc dynamic-pvc | sed -n '/^Events:/,$p'
  Normal  WaitForFirstConsumer   ...  waiting for first consumer to be created before binding
  Normal  ExternalProvisioning   ...  Waiting for a volume to be created either by the external provisioner 'rancher.io/local-path' ...
  Normal  Provisioning           ...  External provisioner is provisioning volume for claim "default/dynamic-pvc"
  Normal  ProvisioningSucceeded  ...  Successfully provisioned volume pvc-aa7f8795-8a90-4708-9d4b-d3988f54aa8c
```

The mini project's claim on `hw-legacy` shows where that storage physically
lives. The provisioner's config points at a directory on the node, and each PV
is a subdirectory named `<pv>_<namespace>_<claim>`:

```console
$ kubectl get pv            (claims from other namespaces omitted)
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                        STORAGECLASS
pvc-80417924-edfd-4197-94de-c19ea7cfd7d7   500Mi      RWO            Delete           Bound    production-webapp/web-data   standard

$ kubectl -n local-path-storage get cm local-path-config -o jsonpath='{.data.config\.json}'
{
        "nodePathMap":[
        {
                "node":"DEFAULT_PATH_FOR_NON_LISTED_NODES",
                "paths":["/var/local-path-provisioner"]
        }
        ]
}

$ docker exec hw-legacy-control-plane sh -c 'ls -l /var/local-path-provisioner/'
drwxrwxrwx 2 root root 4096 Oct  7 13:31 pvc-80417924-edfd-4197-94de-c19ea7cfd7d7_production-webapp_web-data
```

The PV name is `pvc-<claim UID>`. It is exactly the requested size (500Mi,
nothing wasted) and has inherited `Delete` from the class.

### Static vs dynamic

| | Static | Dynamic |
|---|---|---|
| Who creates the PV | an admin, in advance | the provisioner, when a claim needs it |
| Size | whatever PV happens to fit (500Mi claim got 1Gi) | exactly what was requested |
| Reclaim policy | set per PV (`Retain` here) | inherited from the StorageClass (`Delete` here) |
| Scales to many apps | no | yes, which is why production clusters use it |

---

## Summary of what I learned

1. **Lifetime is the deciding question.** emptyDir lives as long as the pod,
   hostPath as long as the node, a PV as long as you keep it.
2. **PV = supply, PVC = request, Pod → PVC.** Pods never name a PV, which keeps
   app manifests portable.
3. **A StorageClass turns a request into supply automatically.** With dynamic
   provisioning the PV appears on its own, sized exactly.
4. **`Pending` with `WaitForFirstConsumer` is normal.** The volume waits for the
   scheduler so it gets created on the node or zone where the pod will run.
5. **Reclaim policy decides whether data survives deleting the claim.**
   `Delete` is the usual dynamic default. Use `Retain` for anything you can't
   rebuild.
6. **RWO means one node, not one pod.** Both mini-project replicas mounted the
   same RWO claim because they ran on the same node.
