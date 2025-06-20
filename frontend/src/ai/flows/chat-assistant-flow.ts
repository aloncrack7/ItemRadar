'use server';
/**
 * @fileOverview A conversational AI assistant for reporting lost or found items.
 *
 * - chatAssistantFlow - Handles the conversation for reporting items.
 * - ChatAssistantFlowInput - The input type for the flow.
 * - ChatAssistantFlowOutput - The return type for the flow.
 */

import { ai } from '@/ai/genkit';
import {
  ChatAssistantFlowInputSchema,
  ChatAssistantFlowOutputSchema,
  ChatAssistantFlowInput,
  ChatAssistantFlowOutput,
  ChatHistoryMessageSchema,
} from './chat-assistant-flow-schemas';

const prompt = ai.definePrompt({
  name: 'chatAssistantPrompt',
  input: { schema: ChatAssistantFlowInputSchema },
  output: { schema: ChatAssistantFlowOutputSchema },
  prompt: `You are ItemRadar Bot, a friendly and helpful AI assistant for a lost and found application.
Your goal is to guide users through reporting either a '{{itemType}}' item.
Be conversational and empathetic. Ask clarifying questions one or two at a time to gather all necessary details.

Necessary details for a 'lost' item:
1. Item Name (e.g., "red backpack", "iPhone 13", "keys")
2. Detailed Description (color, brand, distinguishing features, specific contents if applicable)
3. Last Seen Location (specific address, area, or landmark)
4. Date and approximate Time Lost (if known)
5. User's Contact Information (email or phone number for notifications - remind them this will be kept private)

Necessary details for a 'found' item:
1. Item Name (e.g., "black wallet", "Samsung earbuds", "stuffed bear")
2. Detailed Description (color, brand, distinguishing features)
3. Found Location (specific address, area, or landmark)
4. Date and approximate Time Found
5. Pickup Instructions / How to Claim (e.g., "Item is at the front desk of City Library", "Contact me to arrange pickup")
6. User's Contact Information (email or phone number for notifications - remind them this will be kept private)

Review the conversation history:
{{#if history}}
Conversation History:
{{#each history}}
{{this.role}}: {{#each this.parts}}{{#if this.text}}{{this.text}}{{else if this.inlineData}}(sent an image){{/if}}{{/each}}
{{/each}}
{{/if}}

User's latest message: {{{userInput}}}
{{#if photoDataUri}}
(The user has also provided an image related to this message. You can acknowledge receiving the image if appropriate.)
{{/if}}

Based on the item type ('{{itemType}}'), the conversation history, and the user's latest message, provide a helpful and concise response.
If the user has just started, greet them and ask your first question based on the item type.
If they provide information, acknowledge it and ask the next relevant question.
If they've provided all necessary details, summarize the report and tell them what happens next (e.g., "Thanks! I have all the details. We'll save this report and notify you if a match is found / someone claims the item.").
Do not ask for information already provided in the history unless clarification is needed.
Keep your responses brief and focused on gathering the next piece of information or confirming completion.
`,
});

const flow = ai.defineFlow(
  {
    name: 'chatAssistantFlow',
    inputSchema: ChatAssistantFlowInputSchema,
    outputSchema: ChatAssistantFlowOutputSchema,
  },
  async (input) => {
    // Construct the prompt input, including history if available
    const promptInput: ChatAssistantFlowInput = {
      userInput: input.userInput,
      itemType: input.itemType,
      photoDataUri: input.photoDataUri,
      history: input.history || [], // Ensure history is an array
    };
    
    // If a photo is provided and not already in history as an image part with text, adjust latest user message in history
    if (input.photoDataUri && input.history) {
      const lastUserMessageIndex = promptInput.history!.findLastIndex(m => m.role === 'user');
      if (lastUserMessageIndex !== -1) {
        const lastUserMessage = promptInput.history![lastUserMessageIndex];
        let hasImagePart = false;
        lastUserMessage.parts.forEach(part => {
          if (part.inlineData) hasImagePart = true;
        });
        // Add image part if not present and userInput is about the image or empty
         if (!hasImagePart && (input.userInput === "(User sent an image)" || !input.userInput)) {
          const imageMimeType = input.photoDataUri.substring(input.photoDataUri.indexOf(':') + 1, input.photoDataUri.indexOf(';'));
          const imageBase64Data = input.photoDataUri.split(',')[1];
          promptInput.history![lastUserMessageIndex].parts.push({ 
            inlineData: { mimeType: imageMimeType, data: imageBase64Data }
          });
        }
      }
    }

    const { output } = await prompt(promptInput);
    if (!output) {
        // Handle cases where output might be null or undefined, e.g. safety reasons
        return { aiResponse: "I'm sorry, I couldn't process that request. Could you try rephrasing?" };
    }
    return { aiResponse: output.aiResponse };
  }
);

// Export as an async function for server actions
export async function chatAssistantFlow(input: ChatAssistantFlowInput): Promise<ChatAssistantFlowOutput> {
  return await flow(input);
}
