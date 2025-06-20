import { ChatInterface } from '@/components/chat/chat-interface';
import { Metadata } from 'next';
import { notFound } from 'next/navigation';

export async function generateMetadata({ params }: { params: { type: string } }): Promise<Metadata> {
  const type = params.type;
  if (type !== 'lost' && type !== 'found') {
    return {
      title: 'Chat Not Found - ItemRadar',
    }
  }
  const capitalizedType = type.charAt(0).toUpperCase() + type.slice(1);
  return {
    title: `Chat About ${capitalizedType} Item - ItemRadar`,
    description: `Chat with our AI assistant to report a ${type} item.`,
  };
}

export default function ChatPage({ params }: { params: { type: string } }) {
  const { type } = params;

  if (type !== 'lost' && type !== 'found') {
    notFound();
  }

  const capitalizedType = type.charAt(0).toUpperCase() + type.slice(1);
  const title = `Report ${capitalizedType} Item`;
  const description = `Chat with our AI assistant to provide details about the item you've ${type}.`;

  return (
    <div className="container mx-auto px-0 py-4 sm:px-4 sm:py-8 flex flex-col h-[calc(100vh-4rem)]">
       <ChatInterface itemType={type as 'lost' | 'found'} title={title} description={description} />
    </div>
  );
}
