import { z } from 'genkit';

export const ChatMessagePartSchema = z.object({
  text: z.string().optional(),
  inlineData: z.object({
    mimeType: z.string(),
    data: z.string(), // Base64 encoded string
  }).optional(),
});

export const ChatHistoryMessageSchema = z.object({
  role: z.enum(['user', 'model', 'system']),
  parts: z.array(ChatMessagePartSchema),
});

export const ChatAssistantFlowInputSchema = z.object({
  userInput: z.string().describe("The user's latest message or query."),
  itemType: z.enum(['lost', 'found']).describe("Whether the user is reporting a 'lost' or 'found' item."),
  photoDataUri: z
    .string()
    .optional()
    .describe(
      "An optional photo of the item, as a data URI that must include a MIME type and use Base64 encoding. Expected format: 'data:<mimetype>;base64,<encoded_data>'."
    ),
  history: z.array(ChatHistoryMessageSchema).optional().describe("The conversation history up to this point."),
});
export type ChatAssistantFlowInput = z.infer<typeof ChatAssistantFlowInputSchema>;

export const ChatAssistantFlowOutputSchema = z.object({
  aiResponse: z.string().describe("The AI assistant's response to the user."),
});
export type ChatAssistantFlowOutput = z.infer<typeof ChatAssistantFlowOutputSchema>; 