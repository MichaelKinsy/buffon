// SPDX-License-Identifier: Apache-2.0
// Faithfulness probe extension: registers one tool. No imports, so every Pi-compatible host loads it the same way.
export default function (pi: any) {
  pi.registerTool({
    name: "fx_tool",
    label: "Fx tool",
    description: "Return a fixed string for the faithfulness probes.",
    parameters: { type: "object", properties: { value: { type: "string" } }, additionalProperties: false },
    async execute() {
      return { content: [{ type: "text", text: "fx tool ok" }], details: {} };
    },
  });
}
