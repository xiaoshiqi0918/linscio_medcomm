import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "MedComm.Bridge",
  async setup() {
    window.addEventListener("message", (event) => {
      if (!event.data) return;

      if (event.data.type === "medcomm:loadWorkflow") {
        const apiWorkflow = event.data.workflow;
        if (!apiWorkflow || typeof apiWorkflow !== "object") return;
        try {
          app.loadApiJson(apiWorkflow, "MedPic Workflow");
        } catch (e) {
          console.warn("[MedComm Bridge] loadApiJson failed, trying widget update:", e);
          updateWidgetsFromApi(apiWorkflow);
        }
      }

      if (event.data.type === "medcomm:updateWidgets") {
        const apiWorkflow = event.data.workflow;
        if (!apiWorkflow || typeof apiWorkflow !== "object") return;
        updateWidgetsFromApi(apiWorkflow);
      }
    });

    function updateWidgetsFromApi(apiWorkflow) {
      const graph = app.graph;
      if (!graph) return;
      const nodes = graph._nodes || graph.nodes || [];
      for (const node of nodes) {
        const nodeId = String(node.id);
        const apiNode = apiWorkflow[nodeId];
        if (!apiNode || !apiNode.inputs) continue;
        if (!node.widgets) continue;
        for (const widget of node.widgets) {
          if (widget.name in apiNode.inputs) {
            const val = apiNode.inputs[widget.name];
            if (typeof val === "string" || typeof val === "number") {
              widget.value = val;
            }
          }
        }
      }
      graph.setDirtyCanvas(true, true);
    }

    if (window.parent !== window) {
      window.parent.postMessage({ type: "medcomm:comfyReady" }, "*");
    }
  },
});
