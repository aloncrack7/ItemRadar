"use server";

import { z } from 'zod';
import { lostItemSchema, foundItemSchema } from '@/lib/schemas';
import type { LostItemFormValues, FoundItemFormValues } from '@/lib/schemas';

// API base URL - adjust based on your setup
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Helper function to make API calls
async function callAPI<T>(endpoint: string, data: any): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
    credentials: 'include'
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API call failed: ${response.status}`);
  }

  return response.json();
}

// Helper function to process images for API
function processImagesForAPI(images: File[]): string[] {
  // In a real implementation, you would upload images to storage
  // and return URLs. For now, we'll return empty array
  // TODO: Implement image upload to cloud storage
  return [];
}

export async function reportLostItemAction(
  data: LostItemFormValues
): Promise<{ success: boolean; message: string; search_id?: string }> {
  try {
    const validatedData = lostItemSchema.parse(data);
    
    // Process images
    const imageUrls = processImagesForAPI(validatedData.images || []);
    
    // Call the API
    const apiData = {
      itemName: validatedData.itemName,
      description: validatedData.description,
      lastSeenLocation: validatedData.lastSeenLocation,
      contactInfo: validatedData.contactInfo,
      images: imageUrls,
    };

    const result = await callAPI<{ success: boolean; message: string; search_id?: string }>(
      '/api/lost-item',
      apiData
    );

    return result;
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error("Validation error (lost item):", error.errors);
      return { success: false, message: `Validation failed: ${error.errors.map(e => e.message).join(', ')}` };
    }
    console.error("Error reporting lost item:", error);
    return { success: false, message: "An unexpected error occurred while reporting the lost item." };
  }
}

export async function reportFoundItemAction(
  data: FoundItemFormValues
): Promise<{ success: boolean; message: string; item_id?: string }> {
  try {
    const validatedData = foundItemSchema.parse(data);
    
    // Process images
    const imageUrls = processImagesForAPI(validatedData.images || []);
    
    // Call the API
    const apiData = {
      itemName: validatedData.itemName,
      description: validatedData.description,
      foundLocation: validatedData.foundLocation,
      pickupInstructions: validatedData.pickupInstructions,
      contactInfo: validatedData.contactInfo,
      images: imageUrls,
    };

    const result = await callAPI<{ success: boolean; message: string; item_id?: string }>(
      '/api/found-item',
      apiData
    );

    return result;
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error("Validation error (found item):", error.errors);
      return { success: false, message: `Validation failed: ${error.errors.map(e => e.message).join(', ')}` };
    }
    console.error("Error reporting found item:", error);
    return { success: false, message: "An unexpected error occurred while reporting the found item." };
  }
}

// Helper function to check search status
export async function checkSearchStatusAction(
  searchId: string
): Promise<{ success: boolean; status?: string; matches_found?: number }> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/search-status/${searchId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to check search status: ${response.status}`);
    }

    const result = await response.json();
    return { success: true, ...result };
  } catch (error) {
    console.error("Error checking search status:", error);
    return { success: false };
  }
}
