import { JobDetailClient } from "./JobDetailClient";

export function generateStaticParams() {
  // placeholder — real IDs are resolved client-side via the FastAPI catch-all
  return [{ id: "_" }];
}

export default function Page({ params }: { params: { id: string } }) {
  return <JobDetailClient id={params.id} />;
}
