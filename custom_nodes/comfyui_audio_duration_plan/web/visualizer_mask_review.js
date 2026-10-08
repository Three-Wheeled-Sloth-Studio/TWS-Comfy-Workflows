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
            const savedImage = this.widgets?.find((widget) => widget.name === "image");
            if (savedImage) {
                savedImage.type = "local-visualizer-mask-state";
                savedImage.computeSize = () => [0, -4];
            }
        };
    },
});
