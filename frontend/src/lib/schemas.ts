import { z } from 'zod';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"];

const fileSchema = z.custom<File>((file) => file instanceof File, "File is required.")
  .refine((file) => file.size <= MAX_FILE_SIZE, `Max file size is 5MB.`)
  .refine(
    (file) => ACCEPTED_IMAGE_TYPES.includes(file.type),
    ".jpg, .jpeg, .png and .webp files are accepted."
  );

export const itemBaseSchema = z.object({
  itemName: z.string().min(2, { message: "Item name must be at least 2 characters." }).max(100),
  description: z.string().min(10, { message: "Description must be at least 10 characters." }).max(500),
  contactInfo: z.string().min(5, { message: "Contact information is required." })
    .max(100, { message: "Contact information is too long."}),
  images: z.array(fileSchema).max(4, { message: "You can upload a maximum of 4 images." }).optional(),
});

export const lostItemSchema = itemBaseSchema.extend({
  lastSeenLocation: z.string().min(3, { message: "Location must be at least 3 characters." }).max(200),
});

export const foundItemSchema = itemBaseSchema.extend({
  foundLocation: z.string().min(3, { message: "Location must be at least 3 characters." }).max(200),
  pickupInstructions: z.string().min(10, { message: "Pickup instructions must be at least 10 characters." }).max(500),
});

export type LostItemFormValues = z.infer<typeof lostItemSchema>;
export type FoundItemFormValues = z.infer<typeof foundItemSchema>;
