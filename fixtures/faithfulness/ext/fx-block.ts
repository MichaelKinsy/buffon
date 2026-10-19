// SPDX-License-Identifier: Apache-2.0
// Faithfulness probe extension: blocks every tool call from a tool_call handler.
export default function (pi: any) {
  pi.on("tool_call", async () => ({ block: true, reason: "blocked by fx" }));
}
