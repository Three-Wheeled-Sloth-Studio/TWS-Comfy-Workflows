import { app } from "../../scripts/app.js";

const DRIVERS = [
    "beat", "energy", "low", "mid", "high", "kick", "snare", "hihat",
    "onset", "beat_phase", "phrase", "slow", "vocal_energy", "instrument_energy",
];

const number = (name, label, value, min, max, step, section = "Response") => (
    { name, label, type: "number", default: value, min, max, step, section }
);
const choice = (name, label, value, values, section = "Source & grouping") => (
    { name, label, type: "select", default: value, values, section }
);
const toggle = (name, label, value, section = "Appearance") => (
    { name, label, type: "checkbox", default: value, section }
);
const text = (name, label, value, section = "Source & grouping") => (
    { name, label, type: "text", default: value, section }
);

const RESPONSE_FIELDS = [
    choice("secondary_audio_driver", "Secondary audio driver", "none", ["none", ...DRIVERS]),
    number("secondary_driver_mix", "Secondary driver mix", 0, 0, 1, 0.05),
    number("response_attack_ms", "Attack (ms)", 80, 0, 2000, 5),
    number("response_decay_ms", "Decay (ms)", 260, 5, 4000, 5),
    number("response_hold_ms", "Hold (ms)", 0, 0, 2000, 5),
    number("response_sustain", "Sustain", 0, 0, 1, 0.05),
    number("response_release_ms", "Release (ms)", 420, 5, 6000, 5),
    number("response_smoothing", "Smoothing", 0.2, 0, 0.98, 0.01),
    number("response_min", "Response minimum", 0, 0, 1, 0.01),
    number("response_max", "Response maximum", 1, 0, 1, 0.01),
    number("response_sensitivity", "Sensitivity", 1, 0, 3, 0.05),
    number("response_curve", "Response curve", 1, 0.2, 4, 0.05),
    choice("rhythmic_subdivision", "Rhythmic subdivision", 1, [1, 2, 4]),
    number("accent_weight", "Accent weight", 0, 0, 1, 0.05),
    number("group_gain", "Group gain", 1, 0, 2, 0.05),
    number("group_delay_ms", "Group delay (ms)", 0, -1000, 2000, 10),
    number("section_response", "Section response", 0, 0, 1, 0.05),
];

const GENERAL_FIELDS = [
    { ...text("target_id", "Target ID", "manual_target"), source: "widget" },
    { ...text("linked_group", "Linked group", "independent"), source: "widget" },
    choice("audio_driver", "Primary audio driver", "beat", DRIVERS),
    number("on_beat_motion", "On-beat motion boost", 0, 0, 2, 0.05, "Motion"),
    { ...number("glow_radius_px", "Glow radius (px)", 0, 0, 160, 1, "Appearance"), source: "widget" },
    { ...number("saturation_variation", "Saturation variation", 0, -0.5, 0.5, 0.01, "Appearance"), source: "widget" },
    { ...number("hue_variation_degrees", "Hue variation (degrees)", 0, -30, 30, 0.5, "Appearance"), source: "widget" },
    choice("approved_mask_mode", "Mask combination", "add", ["add", "subtract", "replace"], "Appearance"),
    number("lighting_gain", "Lighting gain", 1, 0, 3, 0.05, "Appearance"),
    toggle("edge_glow_enabled", "Edge glow", false),
    number("edge_glow_amount", "Edge glow amount", 0, 0, 1, 0.05, "Appearance"),
    toggle("shimmer_enabled", "Shimmer", false),
    number("shimmer_amount", "Shimmer amount", 0, 0, 1, 0.05, "Appearance"),
    ...RESPONSE_FIELDS,
];

const ATMOSPHERE_FIELDS = [
    { ...text("target_id", "Target ID", "manual_smoke"), source: "widget" },
    text("envelope_group", "Envelope group", "atmosphere"),
    choice("audio_driver", "Primary audio driver", "slow", DRIVERS),
    choice("atmospheric_motion_mode", "Atmospheric motion mode", "procedural", ["auto", "procedural", "cached_clip", "cached_clip_then_procedural"], "Motion"),
    text("generated_clip_path", "Generated clip path (optional)", "", "Cached clip"),
    number("generated_clip_max_seconds", "Generated clip max seconds", 6, 0.25, 10, 0.25, "Cached clip"),
    number("generated_clip_overlap_seconds", "Loop overlap seconds", 0.6, 0, 3, 0.05, "Cached clip"),
    ...RESPONSE_FIELDS.map((field) => ({
        ...field,
        default: ({
            response_attack_ms: 220, response_decay_ms: 620, response_hold_ms: 80,
            response_sustain: 0.3, response_release_ms: 1150, response_smoothing: 0.42,
            response_min: 0.12, response_max: 0.78, response_sensitivity: 0.9,
            response_curve: 1.15,
        })[field.name] ?? field.default,
    })),
];

function hideWidget(widget) {
    if (!widget || widget._infraChoirHidden) return;
    widget._infraChoirHidden = true;
    // Keep the original widget type. ComfyUI uses it to decide which values
    // and input declarations are serialized; changing it visually hid the
    // row but caused later values to shift into the wrong fields on save.
    widget.computeSize = () => [0, -4];
}

function readJson(widget) {
    try {
        const value = JSON.parse(String(widget?.value || "{}"));
        return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch (_) {
        return {};
    }
}

function createControl(field, value) {
    const input = document.createElement(field.type === "select" ? "select" : "input");
    if (field.type === "select") {
        for (const optionValue of field.values) {
            const option = document.createElement("option");
            option.value = String(optionValue);
            option.textContent = String(optionValue);
            input.append(option);
        }
        input.value = String(value);
    } else {
        input.type = field.type;
        if (field.type === "checkbox") input.checked = Boolean(value);
        else input.value = value ?? "";
        if (field.type === "number") {
            input.min = field.min;
            input.max = field.max;
            input.step = field.step;
        }
    }
    input.dataset.setting = field.name;
    return input;
}

function openAdvancedSettings(node, fields, introduction) {
    const jsonWidget = node.widgets?.find((widget) => widget.name === "advanced_settings_json");
    const saved = readJson(jsonWidget);
    const overlay = document.createElement("div");
    overlay.className = "infra-choir-advanced-overlay";
    const panel = document.createElement("div");
    panel.className = "infra-choir-advanced-panel";
    const heading = document.createElement("h2");
    heading.textContent = `Advanced Settings — ${node.widgets?.find((widget) => widget.name === "object_name")?.value || "effect"}`;
    panel.append(heading);
    const help = document.createElement("p");
    help.className = "infra-choir-advanced-help";
    help.textContent = introduction;
    panel.append(help);

    let sectionName = null;
    const controls = new Map();
    for (const field of fields) {
        if (field.section !== sectionName) {
            sectionName = field.section;
            const section = document.createElement("h3");
            section.textContent = sectionName;
            panel.append(section);
        }
        const row = document.createElement("label");
        row.className = "infra-choir-advanced-row";
        const caption = document.createElement("span");
        caption.textContent = field.label;
        const directWidget = field.source === "widget"
            ? node.widgets?.find((widget) => widget.name === field.name)
            : null;
        const value = directWidget ? directWidget.value : (saved[field.name] ?? field.default);
        const control = createControl(field, value);
        controls.set(field.name, { control, field, directWidget });
        row.append(caption, control);
        panel.append(row);
    }

    const actions = document.createElement("div");
    actions.className = "infra-choir-advanced-actions";
    const cancel = document.createElement("button");
    cancel.textContent = "Cancel";
    const save = document.createElement("button");
    save.textContent = "Save settings";
    save.className = "infra-choir-advanced-save";
    actions.append(cancel, save);
    panel.append(actions);
    overlay.append(panel);
    document.body.append(overlay);

    const close = () => overlay.remove();
    cancel.addEventListener("click", close);
    overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
    save.addEventListener("click", () => {
        const next = { ...saved };
        for (const { control, field, directWidget } of controls.values()) {
            let value;
            if (field.type === "checkbox") value = control.checked;
            else if (field.type === "number") value = Number(control.value);
            else if (field.type === "select" && typeof field.default === "number") value = Number(control.value);
            else value = control.value;
            if (directWidget) {
                directWidget.value = value;
                directWidget.callback?.(value, node, directWidget);
            } else {
                next[field.name] = value;
            }
        }
        if (jsonWidget) {
            jsonWidget.value = JSON.stringify(next);
            jsonWidget.callback?.(jsonWidget.value, node, jsonWidget);
        }
        node.graph?.change?.();
        node.graph?.setDirtyCanvas?.(true, true);
        close();
    });
}

function installStyles() {
    if (document.getElementById("infra-choir-advanced-styles")) return;
    const style = document.createElement("style");
    style.id = "infra-choir-advanced-styles";
    style.textContent = `
        .infra-choir-advanced-overlay { position: fixed; inset: 0; z-index: 10000; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.68); }
        .infra-choir-advanced-panel { width: min(720px, 90vw); max-height: 86vh; overflow: auto; padding: 22px 26px; color: #eee; background: #20252b; border: 1px solid #6785a0; border-radius: 10px; box-shadow: 0 18px 70px rgba(0,0,0,.55); font: 14px sans-serif; }
        .infra-choir-advanced-panel h2 { margin: 0 0 18px; font-size: 19px; }
        .infra-choir-advanced-help { margin: -8px 0 18px; color: #c4ccd3; line-height: 1.45; }
        .infra-choir-advanced-panel h3 { margin: 20px 0 8px; padding-bottom: 5px; color: #a9c8e2; border-bottom: 1px solid #46535f; font-size: 14px; }
        .infra-choir-advanced-row { display: grid; grid-template-columns: minmax(210px, 1fr) minmax(190px, 1fr); align-items: center; gap: 18px; padding: 5px 0; }
        .infra-choir-advanced-row input, .infra-choir-advanced-row select { box-sizing: border-box; width: 100%; min-height: 30px; padding: 4px 7px; color: #eee; background: #15191d; border: 1px solid #56636f; border-radius: 4px; }
        .infra-choir-advanced-row input[type=checkbox] { width: 20px; justify-self: start; }
        .infra-choir-advanced-actions { position: sticky; bottom: -22px; display: flex; justify-content: flex-end; gap: 10px; margin: 24px -26px -22px; padding: 14px 26px; background: #20252b; border-top: 1px solid #46535f; }
        .infra-choir-advanced-actions button { padding: 8px 14px; color: #eee; background: #39434d; border: 1px solid #687987; border-radius: 5px; cursor: pointer; }
        .infra-choir-advanced-actions .infra-choir-advanced-save { background: #28668f; border-color: #4f9bcb; }
    `;
    document.head.append(style);
}

function restoreNamedWidgetValues(node, serializedNode) {
    const namedValues = serializedNode?.widgets_values_named;
    if (!namedValues || typeof namedValues !== "object" || Array.isArray(namedValues)) return;
    for (const widget of node.widgets ?? []) {
        if (!Object.prototype.hasOwnProperty.call(namedValues, widget.name)) continue;
        widget.value = namedValues[widget.name];
    }
}

function serializeNamedWidgetValues(node, serializedNode) {
    const namedValues = {};
    for (const widget of node.widgets ?? []) {
        if (!widget?.name || widget.options?.serialize === false || widget.type === "button") continue;
        namedValues[widget.name] = widget.value;
    }
    serializedNode.widgets_values_named = namedValues;
}

app.registerExtension({
    name: "comfyui_audio_duration_plan.infra_choir_manual_advanced",
    setup() { installStyles(); },
    beforeRegisterNodeDef(nodeType, nodeData) {
        const atmosphere = nodeData.name === "InfraChoirManualAtmosphereTarget";
        const compact = nodeData.name === "InfraChoirManualTargetCompact";
        const detector = nodeData.name === "VisualizerManualTargetDetector";
        if (!atmosphere && !compact && !detector) return;
        const originalConfigure = nodeType.prototype.onConfigure;
        const originalSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onConfigure = function (serializedNode) {
            originalConfigure?.apply(this, arguments);
            restoreNamedWidgetValues(this, serializedNode);
        };
        nodeType.prototype.onSerialize = function (serializedNode) {
            originalSerialize?.apply(this, arguments);
            serializeNamedWidgetValues(this, serializedNode);
        };
        if (detector) return;
        const baseFields = atmosphere ? ATMOSPHERE_FIELDS : GENERAL_FIELDS;
        const baseHiddenNames = [
            "advanced_settings_json",
            "target_id",
            ...(atmosphere ? [] : ["linked_group", "glow_radius_px", "saturation_variation", "hue_variation_degrees"]),
        ];
        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            originalCreated?.apply(this, arguments);
            const hiddenNames = new Set(baseHiddenNames);
            const role = String(this.widgets?.find((widget) => widget.name === "target_role")?.value || "organic");
            const fields = atmosphere ? baseFields : baseFields.filter((field) => {
                if (field.name === "on_beat_motion") return role === "organic";
                if (["shimmer_enabled", "shimmer_amount"].includes(field.name)) return role === "reflection";
                if (["glow_radius_px", "lighting_gain"].includes(field.name)) {
                    return ["light_source", "illumination", "reflection"].includes(role);
                }
                if (["saturation_variation", "hue_variation_degrees"].includes(field.name)) return role !== "organic";
                return true;
            });
            if (!atmosphere && role !== "light_source") hiddenNames.add("glow_strength");
            if (!atmosphere && role === "organic") hiddenNames.add("max_luminance_change");
            for (const widget of this.widgets ?? []) {
                if (hiddenNames.has(widget.name)) hideWidget(widget);
            }
            this.addWidget?.("button", "Advanced Settings…", null, () => {
                const introduction = atmosphere
                    ? "Primary smoke behavior is controlled on the card by Smoke intensity, Boundary expansion, and Billow amount. These advanced controls shape its audio response or select an optional cached clip."
                    : role === "light_source"
                        ? "Primary light behavior is controlled on the card by Beat flicker, Ambient flicker, Maximum luminance change, and Glow strength. The source remains spatially still."
                        : role === "reflection"
                            ? "Primary reflection behavior is controlled on the card by flicker and luminance. Shimmer adds a fine high-frequency brightness ripple; it does not move source pixels."
                            : "Primary organic behavior is controlled on the card by Motion type and Motion amount. Advanced response controls shape how strongly the audio modulates it.";
                openAdvancedSettings(this, fields, introduction);
            }, { serialize: false });
            requestAnimationFrame(() => {
                const computed = this.computeSize?.() ?? this.size ?? [500, atmosphere ? 330 : 420];
                this.setSize?.([Math.max(this.size?.[0] ?? 500, 500), Math.max(computed[1], atmosphere ? 310 : 390)]);
                this.graph?.setDirtyCanvas?.(true, true);
            });
        };
    },
});
