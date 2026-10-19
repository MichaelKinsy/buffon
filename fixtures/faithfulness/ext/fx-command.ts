// SPDX-License-Identifier: Apache-2.0
// Faithfulness probe extension: registers a slash command that sends a user message.
export default function (pi: any) {
  pi.registerCommand("fx", {
    description: "Faithfulness probe command",
    handler: async (args: string) => {
      pi.sendUserMessage("fx command ran with: " + args);
    },
  });
}
