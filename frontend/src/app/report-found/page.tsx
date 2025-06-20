import { ItemForm } from '@/components/forms/item-form';
import { foundItemSchema, type FoundItemFormValues } from '@/lib/schemas';
import { reportFoundItemAction } from '@/app/actions';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Report Found Item - ItemRadar',
  description: 'Report an item you have found.',
};

export default function ReportFoundPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <ItemForm<FoundItemFormValues>
        formType="found"
        schema={foundItemSchema}
        onSubmitAction={reportFoundItemAction}
        defaultValues={{
          itemName: '',
          description: '',
          foundLocation: '',
          pickupInstructions: '',
          contactInfo: '',
          images: [],
        }}
      />
    </div>
  );
}
