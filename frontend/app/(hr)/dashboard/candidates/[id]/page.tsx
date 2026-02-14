export default function CandidateDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-bold">Candidate Detail</h1>
      <p className="mt-4 text-muted-foreground">Candidate ID: {params.id}</p>
    </main>
  );
}
