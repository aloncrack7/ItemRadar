
"use client";

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useFormState, useFormStatus } from 'react-dom';
import { Paperclip, Send, Loader2, Image as ImageIcon, XCircle, Camera as CameraIcon, AlertTriangle } from 'lucide-react';
import Image from 'next/image';
import { handleUserMessage } from '@/app/chat/actions';
import type { ChatMessage } from '@/app/chat/actions';
import { ChatMessageBubble } from './chat-message-bubble';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

interface ChatInterfaceProps {
  itemType: 'lost' | 'found';
  title: string;
  description: string;
}

const initialMessages: ChatMessage[] = [];

export function ChatInterface({ itemType, title, description }: ChatInterfaceProps) {
  const { toast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputText, setInputText] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [isCameraDialogOpen, setIsCameraDialogOpen] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [hasCameraPermission, setHasCameraPermission] = useState<boolean | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);


  const [formState, formAction] = useFormState(handleUserMessage, {
    lastMessageId: '',
    aiResponse: null,
    error: null,
  });

  const { pending } = useFormStatus();

   useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        { 
          id: 'initial-ai-message', 
          role: 'assistant', 
          content: [{ type: 'text', text: `Hello! I'm here to help you report your ${itemType} item. To start, please describe the item or upload/take a photo.` }]
        }
      ]);
    }
  }, [itemType, messages.length]);


  useEffect(() => {
    if (formState.aiResponse && formState.lastMessageId && !messages.find(msg => msg.id === formState.lastMessageId)) {
      setMessages(prevMessages => [
        ...prevMessages,
        { id: formState.lastMessageId!, role: 'assistant', content: [{ type: 'text', text: formState.aiResponse! }] }
      ]);
    }
    if (formState.error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: formState.error,
      });
      // Restore user input if submission failed
      const lastUserMessage = messages.find(msg => msg.id.startsWith('user-'));
      if (lastUserMessage && lastUserMessage.content.some(c => c.type === 'text')) {
        setInputText(lastUserMessage.content.find(c => c.type === 'text')?.text || '');
      }
      // Note: Image preview is already handled by `removeImage` on submit, so no need to restore image here.
    }
  }, [formState, toast, messages]);

  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollElement = scrollAreaRef.current.querySelector('div[data-radix-scroll-area-viewport]');
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      }
    }
  }, [messages]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(e.target.value);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { 
        toast({ variant: "destructive", title: "File too large", description: "Please select an image smaller than 5MB." });
        return;
      }
      if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
        toast({ variant: "destructive", title: "Invalid file type", description: "Please select a JPG, PNG, WEBP, or GIF image." });
        return;
      }
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      if (fileInputRef.current) fileInputRef.current.value = ''; // Clear file input
    }
  };

  const removeImage = () => {
    setImageFile(null);
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
      setImagePreview(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!inputText.trim() && !imageFile) return;

    const userMessageId = `user-${Date.now()}`;
    const userMessageContent: ChatMessage['content'] = [];
    if (inputText.trim()) {
      userMessageContent.push({ type: 'text', text: inputText.trim() });
    }
    if (imagePreview && imageFile) { // Ensure imageFile is also present
       userMessageContent.push({ type: 'imageUrl', imageUrl: imagePreview });
    }
    
    const newUserMessage: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: userMessageContent,
    };
    setMessages(prevMessages => [...prevMessages, newUserMessage]);

    const formData = new FormData();
    formData.append('userInput', inputText.trim());
    formData.append('itemType', itemType);
    
    // Include relevant history, exclude the current pending user message from history
    const historyForFlow = messages.filter(m => m.id !== userMessageId).slice(-5);
    formData.append('history', JSON.stringify(historyForFlow)); 

    if (imageFile) {
      formData.append('imageFile', imageFile);
    }
    
    formAction(formData);

    setInputText('');
    removeImage(); // Clears preview and file state
  };

  // Camera Logic
  const stopCameraStream = useCallback(() => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
    }
    if (videoRef.current) {
        videoRef.current.srcObject = null;
    }
  }, [cameraStream]);

  useEffect(() => {
    if (isCameraDialogOpen && cameraStream && videoRef.current) {
        videoRef.current.srcObject = cameraStream;
        videoRef.current.play().catch(e => console.error("Video play error:", e));
    }
    return () => { // Cleanup on unmount or if dialog closes unexpectedly
        if (!isCameraDialogOpen && cameraStream) {
             stopCameraStream();
        }
    };
  }, [isCameraDialogOpen, cameraStream, stopCameraStream]);

  const handleOpenCameraButtonClick = async () => {
    if (imagePreview || pending || isCameraDialogOpen) return;
    setCameraError(null);
    setHasCameraPermission(null);
    setIsCameraDialogOpen(true);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError("Your browser does not support camera access.");
        setHasCameraPermission(false);
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        setCameraStream(stream);
        setHasCameraPermission(true);
    } catch (err) {
        console.error("Error accessing camera:", err);
        let description = 'Could not access camera. Please enable permissions in your browser settings.';
        if (err instanceof Error) {
            if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                description = "Camera access was denied. Please enable it in your browser settings.";
            } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
                description = "No camera found. Ensure a camera is connected and enabled.";
            } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
                description = "Camera is already in use or cannot be read. Try closing other apps using the camera, or check browser permissions.";
            }
        }
        setCameraError(description);
        setHasCameraPermission(false);
    }
  };

  const handleCaptureImage = () => {
    if (videoRef.current && canvasRef.current && cameraStream && videoRef.current.readyState >= videoRef.current.HAVE_METADATA) {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext('2d');
        if (context) {
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            canvas.toBlob((blob) => {
                if (blob) {
                    const fileName = `capture-${Date.now()}.jpg`;
                    const file = new File([blob], fileName, { type: 'image/jpeg' });
                    setImageFile(file);
                    setImagePreview(URL.createObjectURL(file)); 
                }
            }, 'image/jpeg', 0.9);
        }
        handleCloseCameraDialog();
    } else {
        setCameraError("Failed to capture image. Camera not ready or stream inactive.");
        toast({ variant: 'destructive', title: 'Capture Error', description: 'Could not capture image. Please try again.' });
    }
  };

  const handleCloseCameraDialog = () => {
    stopCameraStream();
    setIsCameraDialogOpen(false);
  };
  

  return (
    <>
      <Card className="w-full h-full flex flex-col shadow-2xl rounded-lg overflow-hidden">
        <CardHeader className="bg-primary text-primary-foreground">
          <CardTitle className="font-headline text-2xl">{title}</CardTitle>
          <CardDescription className="text-primary-foreground/90">{description}</CardDescription>
        </CardHeader>
        <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
          <div className="space-y-4">
            {messages.map((msg) => (
              <ChatMessageBubble key={msg.id} message={msg} />
            ))}
            {pending && (
              <div className="flex justify-start">
                  <div className="flex items-center space-x-2 bg-muted p-3 rounded-lg max-w-[70%]">
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                      <span className="text-sm text-muted-foreground">Assistant is typing...</span>
                  </div>
              </div>
            )}
          </div>
        </ScrollArea>
        <CardFooter className="p-4 border-t bg-background">
          <form onSubmit={handleSubmit} className="w-full flex flex-col gap-2">
            {imagePreview && (
              <div className="relative w-24 h-24 mb-2 border rounded-md overflow-hidden self-start">
                <Image src={imagePreview} alt="Selected preview" layout="fill" objectFit="cover" />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute top-0 right-0 h-6 w-6 bg-black/50 hover:bg-black/70 text-white rounded-full z-10"
                  onClick={removeImage}
                  aria-label="Remove image"
                >
                  <XCircle className="h-4 w-4" />
                </Button>
              </div>
            )}
            <div className="flex items-end sm:items-center gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/png, image/jpeg, image/webp, image/gif"
                className="hidden"
                disabled={pending || !!imageFile || isCameraDialogOpen}
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={pending || !!imageFile || isCameraDialogOpen}
                className="shrink-0"
                aria-label="Attach image"
              >
                <Paperclip className="h-5 w-5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handleOpenCameraButtonClick}
                disabled={pending || !!imageFile || isCameraDialogOpen}
                className="shrink-0"
                aria-label="Take photo"
              >
                <CameraIcon className="h-5 w-5" />
              </Button>
              <Input
                type="text"
                placeholder="Type your message..."
                value={inputText}
                onChange={handleInputChange}
                disabled={pending || isCameraDialogOpen}
                className="flex-grow min-w-0"
                aria-label="Message input"
              />
              <Button type="submit" size="icon" disabled={pending || (!inputText.trim() && !imageFile) || isCameraDialogOpen} className="shrink-0" aria-label="Send message">
                {pending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </Button>
            </div>
          </form>
        </CardFooter>
      </Card>

      <Dialog open={isCameraDialogOpen} onOpenChange={(open) => { if (!open) handleCloseCameraDialog(); }}>
        <DialogContent className="sm:max-w-md p-0">
          <DialogHeader className="p-4 pb-0">
            <DialogTitle>Take Photo</DialogTitle>
          </DialogHeader>
          <div className="p-4 space-y-4">
            <div className="w-full aspect-video bg-muted rounded-md overflow-hidden relative">
              <video ref={videoRef} className="w-full h-full object-cover" autoPlay muted playsInline />
              {isCameraDialogOpen && !cameraStream && !cameraError && hasCameraPermission !== false && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70">
                  <Loader2 className="h-8 w-8 animate-spin text-white" />
                  <p className="mt-2 text-white">Initializing camera...</p>
                </div>
              )}
            </div>
            
            {cameraError && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Camera Error</AlertTitle>
                <AlertDescription>{cameraError}</AlertDescription>
              </Alert>
            )}
            {hasCameraPermission === false && !cameraError && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Camera Access Required</AlertTitle>
                <AlertDescription>
                  Camera access was denied or is unavailable. Please enable camera permissions in your browser settings and ensure a camera is connected.
                </AlertDescription>
              </Alert>
            )}
            <canvas ref={canvasRef} className="hidden"></canvas>
          </div>
          <DialogFooter className="p-4 pt-0 flex sm:justify-between">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button 
              type="button" 
              onClick={handleCaptureImage} 
              disabled={!cameraStream || !!cameraError || hasCameraPermission === false}
            >
              <CameraIcon className="mr-2 h-4 w-4" /> Capture
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

