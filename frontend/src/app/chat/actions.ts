"use server";

import { z } from 'zod';

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
  imageFile: z
    .any()
    .transform(val => (val instanceof File ? val : undefined))
    .refine(file => !file || file.size <= MAX_FILE_SIZE, `Max file size is 5MB.`)
    .refine(file => !file || ACCEPTED_IMAGE_TYPES.includes(file.type), `Accepted image types: JPG, PNG, WEBP, GIF.`)
    .optional(),
});

// Function to call the multi-agent system via API
async function callMultiAgentSystem(input: {
  userInput: string;
  itemType: 'lost' | 'found';
  photoDataUri?: string;
  history?: ChatMessage[];
}): Promise<{ aiResponse: string }> {
  try {
    // Get the API URL from environment or use default
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    // Prepare the request payload
    const payload = {
      user_input: input.userInput,
      item_type: input.itemType,
      photo_data_uri: input.photoDataUri,
      history: input.history?.map(msg => ({
        role: msg.role,
        content: msg.content.map(part => ({
          type: part.type,
          text: part.text || '',
          image_url: part.imageUrl || ''
        }))
      })) || []
    };

    // Make the API call
    const response = await fetch(`${apiUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Unknown error from multi-agent system');
    }

    return { aiResponse: result.response };
  } catch (error) {
    console.error('Error calling multi-agent system:', error);
    throw new Error(`Failed to communicate with AI system: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

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

  // If user only sent an image, add a placeholder text for userInput
  const finalUserInput = userInput || (photoDataUri ? "(User sent an image)" : "");

  try {
    const output = await callMultiAgentSystem({
      userInput: finalUserInput,
      itemType,
      photoDataUri,
      history: history || []
    });
    
    const aiMessageId = `ai-${Date.now()}`;
    return {
      lastMessageId: aiMessageId,
      aiResponse: output.aiResponse,
    };
  } catch (error) {
    console.error('Error calling multi-agent system:', error);
    return {
      error: error instanceof Error ? error.message : 'Sorry, I encountered an issue. Please try again.',
    };
  }
}
