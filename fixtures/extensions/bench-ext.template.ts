// SPDX-License-Identifier: MIT
// One of a numbered set of identical, trivial extensions for the Buffon overhead bench: a tool, a command and four event handlers.
// It uses no imports, so Pi, PiG and any Pi-compatible host load it the same way. buffon/fixtures/benchext.py writes the numbered set from this file, with the extension's number in place of each double-braced NN.
export default function (pi: any) {
  let events = 0;
  pi.registerTool({
    name: "bench_tool_{{NN}}",
    label: "Bench tool {{NN}}",
    description: "Return a fixed string. Used by the overhead bench only.",
    parameters: { type: "object", properties: { value: { type: "string" } }, additionalProperties: false },
    async execute() {
      return { content: [{ type: "text", text: "bench {{NN}} ok" }], details: { events } };
    },
  });
  pi.registerCommand("bench-{{NN}}", {
    description: "Bench command {{NN}}",
    handler: async () => {},
  });
  for (const name of ["session_start", "before_agent_start", "tool_call", "turn_end"]) {
    pi.on(name, async () => {
      events += 1;
    });
  }
}
