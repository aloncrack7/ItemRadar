"use server";

import { z } from 'zod';
import { chatAssistantFlow } from '@/ai/flows/chat-assistant-flow';
import type { ChatAssistantFlowInput, ChatAssistantFlowOutput } from '@/ai/flows/chat-assistant-flow';

export interface ChatMessageContentPart {
  type: 'text' | 'imageUrl';
  text?: string;
  imageUrl?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: ChatMessageContentPart[];
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"];

// Function to convert File to Data URI
async function fileToDataUri(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  return `data:${file.type};base64,${buffer.toString('base64')}`;
}

const chatFormSchema = z.object({
  userInput: z.string().optional(),
  itemType: z.enum(['lost', 'found']),
  history: z.string().transform((str, ctx) => {
    try {
      return JSON.parse(str) as ChatMessage[];
    } catch (e) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Invalid JSON for history" });
      return z.NEVER;
    }
  }).optional(),
  imageFile: z.instanceof(File).optional()
    .refine(file => !file || file.size <= MAX_FILE_SIZE, `Max file size is 5MB.`)
    .refine(file => !file || ACCEPTED_IMAGE_TYPES.includes(file.type), `Accepted image types: JPG, PNG, WEBP, GIF.`),
});


export async function handleUserMessage(
  prevState: { lastMessageId?: string; aiResponse?: string | null; error?: string | null },
  formData: FormData
): Promise<{ lastMessageId?: string; aiResponse?: string | null; error?: string | null }> {
  const validatedFields = chatFormSchema.safeParse({
    userInput: formData.get('userInput') as string || '',
    itemType: formData.get('itemType') as 'lost' | 'found',
    history: formData.get('history') as string || '[]',
    imageFile: formData.get('imageFile') as File | undefined,
  });

  if (!validatedFields.success) {
    console.error("Validation errors:", validatedFields.error.flatten().fieldErrors);
    return {
      error: "Invalid input. " + Object.values(validatedFields.error.flatten().fieldErrors).flat().join(' '),
    };
  }
  
  const { userInput, itemType, history, imageFile } = validatedFields.data;

  if (!userInput && !imageFile) {
    return { error: "Please provide a message or an image." };
  }

  let photoDataUri: string | undefined = undefined;
  if (imageFile) {
    try {
      photoDataUri = await fileToDataUri(imageFile);
    } catch (e) {
      console.error("Error converting file to data URI:", e);
      return { error: "Failed to process image." };
    }
  }

  const flowInput: ChatAssistantFlowInput = {
    userInput: userInput || '',
    itemType,
    photoDataUri,
    history: history?.map(msg => ({
      role: msg.role === 'assistant' ? 'model' : msg.role, // Genkit uses 'model' for assistant
      parts: msg.content.map(part => {
        if (part.type === 'imageUrl' && part.imageUrl && msg.role === 'user' && photoDataUri === part.imageUrl) {
          // This ensures the current uploaded image is passed correctly for the flow
          return { inlineData: { mimeType: imageFile!.type, data: photoDataUri!.split(',')[1] } };
        }
        return { text: part.text || '' };
      }).filter(p => p.text || p.inlineData) // Filter out empty parts
    })).filter(h => h.parts.length > 0) || [],
  };
  
  // If user only sent an image, add a placeholder text for userInput for the flow
  if (!flowInput.userInput && flowInput.photoDataUri) {
    flowInput.userInput = "(User sent an image)";
  }


  try {
    const output: ChatAssistantFlowOutput = await chatAssistantFlow(flowInput);
    const aiMessageId = `ai-${Date.now()}`;
    return {
      lastMessageId: aiMessageId,
      aiResponse: output.aiResponse,
    };
  } catch (error) {
    console.error('Error calling Genkit flow:', error);
    return {
      error: 'Sorry, I encountered an issue. Please try again.',
    };
  }
}
