// SPDX-License-Identifier: Apache-2.0
// Faithfulness probe extension: appends a marker to the system prompt from a before_agent_start handler.
export default function (pi: any) {
  pi.on("before_agent_start", async (event: any) => ({ systemPrompt: event.systemPrompt + "\nFX-MARK-SYSTEM" }));
}
