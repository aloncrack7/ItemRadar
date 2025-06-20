"use server";

import { z } from 'zod';
import { lostItemSchema, foundItemSchema } from '@/lib/schemas';
import type { LostItemFormValues, FoundItemFormValues } from '@/lib/schemas';

// Helper function to simulate backend processing and potential errors
async function processItemReport<T extends LostItemFormValues | FoundItemFormValues>(
  data: T,
  itemType: 'lost' | 'found'
): Promise<{ success: boolean; message: string; data?: T }> {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 1000));

  console.log(`Received ${itemType} item report:`, data);

  // Simulate potential backend validation or processing error
  // if (data.itemName.toLowerCase().includes("test_error")) {
  //   return { success: false, message: `Simulated error processing ${itemType} item: ${data.itemName}` };
  // }

  // For image handling, in a real scenario, you'd upload files to storage (e.g., Firebase Storage)
  // and save URLs or references. For now, we'll just log the file names if present.
  if (data.images && data.images.length > 0) {
    console.log("Uploaded images:");
    data.images.forEach(file => {
      // In a server action, `file` is a File object.
      console.log(`- ${file.name} (type: ${file.type}, size: ${file.size} bytes)`);
    });
    // Here you would typically use a library like @google-cloud/storage or similar
    // to upload `file.stream()` to a bucket.
  }


  return { 
    success: true, 
    message: `Your ${itemType} item report for "${data.itemName}" has been submitted successfully. We will contact you if we have any updates.`,
    data 
  };
}

export async function reportLostItemAction(
  data: LostItemFormValues
): Promise<{ success: boolean; message: string }> {
  try {
    const validatedData = lostItemSchema.parse(data);
    return await processItemReport(validatedData, 'lost');
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
): Promise<{ success: boolean; message: string }> {
  try {
    const validatedData = foundItemSchema.parse(data);
    return await processItemReport(validatedData, 'found');
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error("Validation error (found item):", error.errors);
      return { success: false, message: `Validation failed: ${error.errors.map(e => e.message).join(', ')}` };
    }
    console.error("Error reporting found item:", error);
    return { success: false, message: "An unexpected error occurred while reporting the found item." };
  }
}
