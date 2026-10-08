import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "comfyui_audio_duration_plan.visualizer_mask_review",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "VisualizerMaskReview") {
            return;
        }

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            originalCreated?.apply(this, arguments);
            for (const name of ["image", "source_fingerprint"]) {
                const widget = this.widgets?.find((candidate) => candidate.name === name);
                if (widget) {
                    widget.type = "local-visualizer-mask-state";
                    widget.computeSize = () => [0, -4];
                }
            }
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const state = message?.mask_review_state?.[0];
            if (!state) {
                return;
            }
            let changed = false;
            const fingerprint = this.widgets?.find((widget) => widget.name === "source_fingerprint");
            const nextFingerprint = state.source_fingerprint ?? "";
            if (fingerprint && fingerprint.value !== nextFingerprint) {
                fingerprint.value = nextFingerprint;
                changed = true;
            }
            if (state.clear_saved_mask) {
                const savedImage = this.widgets?.find((widget) => widget.name === "image");
                if (savedImage?.value) {
                    savedImage.value = "";
                    changed = true;
                }
            }
            if (changed) {
                this.graph?.change?.();
                this.graph?.setDirtyCanvas(true, true);
            }
        };
    },
});
