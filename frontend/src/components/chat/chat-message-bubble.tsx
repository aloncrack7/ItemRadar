"use client";

import React from 'react';
import Image from 'next/image';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/app/chat/actions';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { User, Sparkles } from 'lucide-react'; // Using Sparkles for AI

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex items-end gap-2', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <Avatar className="h-8 w-8 self-start">
          <AvatarFallback className="bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          'max-w-[70%] rounded-lg px-3 py-2 text-sm shadow',
          isUser ? 'bg-primary text-primary-foreground rounded-br-none' : 'bg-muted text-foreground rounded-bl-none'
        )}
      >
        {message.content.map((part, index) => {
          if (part.type === 'text') {
            return <p key={index} className="whitespace-pre-wrap">{part.text}</p>;
          }
          if (part.type === 'imageUrl' && part.imageUrl) {
            return (
              <div key={index} className="mt-2 relative aspect-video max-w-xs overflow-hidden rounded-md">
                <Image src={part.imageUrl} alt="User uploaded content" layout="fill" objectFit="contain" />
              </div>
            );
          }
          return null;
        })}
      </div>
      {isUser && (
         <Avatar className="h-8 w-8 self-start">
           <AvatarFallback className="bg-secondary text-secondary-foreground">
            <User className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
