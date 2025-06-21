"use client";

import { useCallback, useState, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import { useDropzone } from 'react-dropzone';
import { UseFormReturn, useController, FieldValues, Path } from 'react-hook-form';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input'; // For styling consistency, though hidden
import { Label } from '@/components/ui/label';
import { X, UploadCloud, FileImage } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ImageUploadFieldProps<T extends FieldValues> {
  name: Path<T>;
  control: UseFormReturn<T>['control'];
  label: string;
  maxFiles?: number;
}

export function ImageUploadField<T extends FieldValues>({
  name,
  control,
  label,
  maxFiles = 4,
}: ImageUploadFieldProps<T>) {
  const { field, fieldState } = useController({ name, control });
  const [previews, setPreviews] = useState<string[]>([]);

  const currentFiles: File[] = field.value || [];

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newFiles = [...currentFiles, ...acceptedFiles].slice(0, maxFiles);
      field.onChange(newFiles);
    },
    [field, currentFiles, maxFiles]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp'] },
    maxFiles,
    multiple: true,
  });

  useEffect(() => {
    const newPreviews = currentFiles.map((file) => URL.createObjectURL(file));
    setPreviews(newPreviews);
    return () => newPreviews.forEach(URL.revokeObjectURL);
  }, [currentFiles]);

  const removeImage = (index: number) => {
    const updatedFiles = currentFiles.filter((_, i) => i !== index);
    field.onChange(updatedFiles);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const filesArray = Array.from(event.target.files);
      const newFiles = [...currentFiles, ...filesArray].slice(0, maxFiles);
      field.onChange(newFiles);
    }
  };

  return (
    <div className="space-y-2">
      <Label htmlFor={name} className={cn(fieldState.error && "text-destructive")}>{label} (Max {maxFiles})</Label>
      <div
        {...getRootProps()}
        className={cn(
          "flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-lg cursor-pointer transition-colors",
          isDragActive ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50',
          fieldState.error && 'border-destructive'
        )}
      >
        <input {...getInputProps({ id: name, onChange: handleFileChange })} />
        <UploadCloud className={cn("w-10 h-10 mb-3", isDragActive ? "text-primary" : "text-muted-foreground")} />
        {isDragActive ? (
          <p className="text-sm text-primary">Drop the files here ...</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Drag & drop some files here, or click to select files
          </p>
        )}
        <p className="text-xs text-muted-foreground">Up to {maxFiles} images, 5MB each</p>
      </div>
      {fieldState.error && (
        <p className="text-sm font-medium text-destructive">
          {fieldState.error.message || (fieldState.error as any)?.root?.message}
        </p>
      )}
      {previews.length > 0 && (
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {previews.map((src, index) => (
            <div key={index} className="relative group aspect-square">
              <Image
                src={src}
                alt={`Preview ${index + 1}`}
                fill
                className="rounded-md object-cover"
              />
              <Button
                type="button"
                variant="destructive"
                size="icon"
                className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={() => removeImage(index)}
                aria-label={`Remove image ${index + 1}`}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
      {currentFiles.length === 0 && previews.length === 0 && (
         <div className="mt-2 flex items-center justify-center text-sm text-muted-foreground">
            <FileImage className="w-4 h-4 mr-2" />
            No images selected.
          </div>
      )}
    </div>
  );
}
