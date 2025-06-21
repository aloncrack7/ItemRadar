"use server";

import { z } from 'zod';
import { cookies } from 'next/headers';

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
const API_TIMEOUT = 30000; // 30 seconds
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

// Function to convert File to Data URI
async function fileToDataUri(file: File): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    return `data:${file.type};base64,${buffer.toString('base64')}`;
  } catch (error) {
    throw new Error(`Failed to convert file to data URI: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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
    .transform(val => (typeof File !== 'undefined' && val instanceof File ? val : undefined))
    .refine(file => !file || file.size <= MAX_FILE_SIZE, `Max file size is 5MB.`)
    .refine(file => !file || ACCEPTED_IMAGE_TYPES.includes(file.type), `Accepted image types: JPG, PNG, WEBP, GIF.`)
    .optional(),
});

// Utility function for delays
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Function to make API request with timeout and retry logic
async function makeApiRequest(url: string, payload: any, retries = MAX_RETRIES): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      credentials: 'include',
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      throw new Error(`API request failed: ${response.status} ${response.statusText}. ${errorText}`);
    }

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.error || 'Unknown error from multi-agent system');
    }

    return result;
  } catch (error) {
    clearTimeout(timeoutId);

    // If it's an abort error (timeout) or network error, retry
    if (retries > 0 && (
      error instanceof Error && (
        error.name === 'AbortError' ||
        error.message.includes('fetch') ||
        error.message.includes('network') ||
        error.message.includes('timeout')
      )
    )) {
      console.warn(`API request failed, retrying in ${RETRY_DELAY}ms. Retries left: ${retries - 1}`);
      await delay(RETRY_DELAY);
      return makeApiRequest(url, payload, retries - 1);
    }

    throw error;
  }
}

// Function to call the multi-agent system via API
async function callMultiAgentSystem(input: {
  userInput: string;
  itemType: 'lost' | 'found';
  photoDataUri?: string;
  history?: ChatMessage[];
}): Promise<{ aiResponse: string }> {
  try {
    // Validate API URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl) {
      throw new Error('API URL is not configured. Please set NEXT_PUBLIC_API_URL environment variable.');
    }

    // Validate URL format
    try {
      new URL(apiUrl);
    } catch {
      throw new Error('Invalid API URL format in NEXT_PUBLIC_API_URL environment variable.');
    }

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

    // Validate payload size (prevent sending overly large requests)
    const payloadSize = JSON.stringify(payload).length;
    const maxPayloadSize = 10 * 1024 * 1024; // 10MB
    if (payloadSize > maxPayloadSize) {
      throw new Error('Request payload is too large. Please reduce the history or image size.');
    }

    const result = await makeApiRequest(`${apiUrl}/api/chat`, payload);

    return { aiResponse: result.response };
  } catch (error) {
    console.error('Error calling multi-agent system:', error);

    // Provide more specific error messages
    if (error instanceof Error) {
      if (error.message.includes('API URL')) {
        throw new Error('Configuration error: API service is not properly configured.');
      } else if (error.message.includes('timeout') || error.name === 'AbortError') {
        throw new Error('The AI service is taking too long to respond. Please try again.');
      } else if (error.message.includes('network') || error.message.includes('fetch')) {
        throw new Error('Unable to connect to the AI service. Please check your internet connection and try again.');
      } else if (error.message.includes('payload')) {
        throw error; // Pass through payload-specific errors
      }
    }

    throw new Error('Sorry, I encountered an issue communicating with the AI service. Please try again.');
  }
}

export async function handleUserMessage(
  prevState: { lastMessageId?: string; aiResponse?: string | null; error?: string | null },
  formData: FormData
): Promise<{ lastMessageId?: string; aiResponse?: string | null; error?: string | null }> {
  try {
    const validatedFields = chatFormSchema.safeParse({
      userInput: formData.get('userInput') as string || '',
      itemType: formData.get('itemType') as 'lost' | 'found',
      history: formData.get('history') as string || '[]',
      imageFile: formData.get('imageFile') as File | undefined,
    });

    if (!validatedFields.success) {
      const errorMessages = Object.values(validatedFields.error.flatten().fieldErrors).flat();
      console.error("Validation errors:", validatedFields.error.flatten().fieldErrors);
      return {
        error: "Invalid input: " + errorMessages.join(', '),
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
      } catch (error) {
        console.error("Error converting file to data URI:", error);
        return {
          error: error instanceof Error ? error.message : "Failed to process the uploaded image. Please try again with a different image."
        };
      }
    }

    // If user only sent an image, add a placeholder text for userInput
    const finalUserInput = userInput || (photoDataUri ? "(User sent an image)" : "");

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
    console.error('Error in handleUserMessage:', error);
    return {
      error: error instanceof Error ? error.message : 'An unexpected error occurred. Please try again.',
    };
  }
}