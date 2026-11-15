"use client";

import { useRouter } from "next/navigation";
import { useFeedback } from "@/components/feedback";
import { ProductionForm, toInput } from "@/components/ProductionForm";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Production } from "@/lib/types";

export default function NewProductionPage() {
  const router = useRouter();
  const { toast } = useFeedback();
  return (
    <>
      <PageHeader title="Yeni oyun" description="Oyun taslak olarak oluşturulur. Afiş ve görselleri bir sonraki adımda ekleyebilirsiniz." />
      <ProductionForm
        initial={toInput(null)}
        submitLabel="Taslağı oluştur"
        onSubmit={async (v) => {
          const rest = { ...v };
          delete rest.slug;
          const p = await api.post<Production>("/admin/productions", rest);
          toast("Oyun taslak olarak oluşturuldu.");
          router.replace(`/oyunlar/${p.id}?sekme=gorseller`);
        }}
      />
    </>
  );
}
