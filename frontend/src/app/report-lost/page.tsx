import { ItemForm } from '@/components/forms/item-form';
import { lostItemSchema, type LostItemFormValues } from '@/lib/schemas';
import { reportLostItemAction } from '@/app/actions';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Report Lost Item - ItemRadar',
  description: 'Report an item you have lost.',
};

export default function ReportLostPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <ItemForm<LostItemFormValues>
        formType="lost"
        schema={lostItemSchema}
        onSubmitAction={reportLostItemAction}
        defaultValues={{
          itemName: '',
          description: '',
          lastSeenLocation: '',
          contactInfo: '',
          images: [],
        }}
      />
    </div>
  );
}
