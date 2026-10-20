import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "comfyui_audio_duration_plan.infra_choir_auto_discover",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "InfraChoirAutoDiscover") {
            return;
        }

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            originalCreated?.apply(this, arguments);
            this._infraChoirManifest = "";
            this._infraChoirReport = "Not run yet. Idle performs no work.";
            this._infraChoirStatusWidget = this.addWidget?.(
                "text", "Last setup result", this._infraChoirReport, () => {}, { serialize: false }
            );
            if (this._infraChoirStatusWidget) {
                this._infraChoirStatusWidget.disabled = true;
            }
            const reviewedWidget = this.widgets?.find((item) => item.name === "reviewed_manifest_json");
            if (reviewedWidget) {
                reviewedWidget._infraChoirOriginalComputeSize = reviewedWidget.computeSize;
                reviewedWidget.computeSize = () => [0, -4];
            }
            this.addWidget?.("button", "Push this discovery into flow", null, async () => {
                if (!this._infraChoirManifest) {
                    app.extensionManager?.toast?.add?.({
                        severity: "warning", summary: "Nothing to push",
                        detail: "Run Discover first.",
                        life: 3500,
                    });
                    return;
                }
                const widget = (name) => this.widgets?.find((item) => item.name === name);
                try {
                    const response = await api.fetchApi("/infra_choir/apply_discovery", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            manifest: this._infraChoirManifest,
                            manifest_path: widget("manifest_path")?.value ?? "infra_choir/auto_targets.json",
                            preserve_reviewed_targets: widget("preserve_reviewed_targets")?.value ?? true,
                        }),
                    });
                    const result = await response.json();
                    if (!response.ok || !result.ok) {
                        throw new Error(result.error || `HTTP ${response.status}`);
                    }
                    this._infraChoirManifest = result.manifest;
                    this._infraChoirReport = result.status;
                    const actionWidget = widget("action");
                    if (actionWidget) {
                        actionWidget.value = "idle";
                    }
                    if (this._infraChoirStatusWidget) {
                        this._infraChoirStatusWidget.value = result.status;
                    }
                    app.extensionManager?.toast?.add?.({
                        severity: "success", summary: "Discovery pushed into flow",
                        detail: `${result.count} target(s) will be used by the next normal workflow run; setup returned to idle.`, life: 6000,
                    });
                    this.graph?.setDirtyCanvas?.(true, true);
                } catch (error) {
                    app.extensionManager?.toast?.add?.({
                        severity: "error", summary: "Could not push discovery",
                        detail: error?.message ?? String(error), life: 7000,
                    });
                }
            }, { serialize: false });
            this.addWidget?.("button", "Copy manifest (advanced)", null, async () => {
                if (!this._infraChoirManifest) return;
                await navigator.clipboard.writeText(this._infraChoirManifest);
            }, { serialize: false });
            this.addWidget?.("button", "Show/hide advanced JSON editor", null, () => {
                if (!reviewedWidget) return;
                reviewedWidget.computeSize = reviewedWidget.computeSize === reviewedWidget._infraChoirOriginalComputeSize
                    ? () => [0, -4]
                    : reviewedWidget._infraChoirOriginalComputeSize;
                this.setSize?.([this.size?.[0] ?? 460, this.computeSize?.()[1] ?? this.size?.[1] ?? 520]);
                this.graph?.setDirtyCanvas?.(true, true);
            }, { serialize: false });
            this.addWidget?.("button", "Copy discovery report", null, async () => {
                await navigator.clipboard.writeText(this._infraChoirReport || "");
            }, { serialize: false });
            this.setSize?.([Math.max(this.size?.[0] ?? 410, 460), Math.max(this.size?.[1] ?? 430, 520)]);
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const state = message?.infra_choir_setup?.[0];
            if (!state) {
                return;
            }
            this._infraChoirManifest = state.manifest ?? "";
            this._infraChoirReport = state.status ?? "Setup action completed.";
            if (this._infraChoirStatusWidget) {
                this._infraChoirStatusWidget.value = this._infraChoirReport.split("\n", 1)[0];
            }
            app.extensionManager?.toast?.add?.({
                severity: state.action === "idle" ? "info" : "success",
                summary: `Infra Choir setup: ${state.action ?? "complete"}`,
                detail: this._infraChoirReport.split("\n", 1)[0],
                life: 6000,
            });
            this.graph?.setDirtyCanvas?.(true, true);
        };
    },
});
