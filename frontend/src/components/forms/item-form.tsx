"use client";

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { ImageUploadField } from './image-upload-field';
import type { LostItemFormValues, FoundItemFormValues } from '@/lib/schemas';
import { Loader2 } from 'lucide-react';
import React from 'react';

type ItemFormProps<T extends LostItemFormValues | FoundItemFormValues> = {
  formType: 'lost' | 'found';
  schema: z.ZodType<T>;
  onSubmitAction: (data: T) => Promise<{ success: boolean; message: string }>;
  defaultValues?: Partial<T>;
};

export function ItemForm<T extends LostItemFormValues | FoundItemFormValues>({
  formType,
  schema,
  onSubmitAction,
  defaultValues,
}: ItemFormProps<T>) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submissionMessage, setSubmissionMessage] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const form = useForm<T>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues || {},
    mode: "onBlur",
  });

  const { toast } = (window as any).useToast ? (window as any).useToast() : { toast: () => {} };


  async function onSubmit(values: T) {
    setIsSubmitting(true);
    setSubmissionMessage(null);
    try {
      // Simulate API call delay for demonstration
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Convert File objects to something serializable if needed, or handle FormData
      // For server actions, File objects can often be passed directly.
      const result = await onSubmitAction(values);

      if (result.success) {
        toast({
          title: "Success!",
          description: result.message,
        });
        form.reset();
        // Clear file previews if ImageUploadField doesn't do it automatically on reset
        // This might require a ref to ImageUploadField or a more integrated state management
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: result.message,
        });
      }
    } catch (error) {
      console.error("Submission error:", error);
      toast({
        variant: "destructive",
        title: "Submission Failed",
        description: "An unexpected error occurred. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  const title = formType === 'lost' ? 'Report a Lost Item' : 'Report a Found Item';
  const description = formType === 'lost'
    ? 'Please provide as much detail as possible about the item you lost.'
    : 'Thank you for reporting an item you found! Please provide details to help us reunite it with its owner.';

  return (
    <Card className="w-full max-w-2xl mx-auto my-8 shadow-lg">
      <CardHeader>
        <CardTitle className="font-headline text-3xl text-primary">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="space-y-6">
            <FormField
              control={form.control}
              name="itemName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Item Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g., Red Backpack, Keys, iPhone 13" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Provide a detailed description (color, brand, distinguishing features, etc.)"
                      className="resize-none"
                      rows={4}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name={formType === 'lost' ? 'lastSeenLocation' : 'foundLocation'}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{formType === 'lost' ? 'Last Seen Location' : 'Found Location'}</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g., Central Park near the fountain, Main Street bus stop" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            {formType === 'found' && (
              <FormField
                control={form.control}
                name="pickupInstructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pickup Instructions / How to Claim</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="e.g., Item is at the front desk of City Library, contact me to arrange pickup"
                        className="resize-none"
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={form.control}
              name="contactInfo"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Your Contact Information (Email or Phone)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g., user@example.com or 555-123-4567" {...field} />
                  </FormControl>
                  <FormDescription>
                    This will be used to contact you about the item. It will not be publicly displayed.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <ImageUploadField
                name="images"
                control={form.control as any} // Cast because T might not have 'images' but schemas do
                label="Upload Images (Optional)"
            />

          </CardContent>
          <CardFooter className="flex flex-col items-stretch gap-4">
             {submissionMessage && (
              <div className={`p-3 rounded-md text-sm ${submissionMessage.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                {submissionMessage.text}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                'Submit Report'
              )}
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}
