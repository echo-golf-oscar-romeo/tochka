import Upload from "@/components/Upload";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-24">
      <div className="max-w-prose w-full">
        <h1 className="font-serif text-5xl leading-tight tracking-tight mb-6">Tochka</h1>
        <p className="text-lg text-muted mb-10">
          Upload a CSV of your network of locations. An agent will decide the methodology and
          produce a storymap with concrete next steps.
        </p>
        <Upload />
        <p className="text-xs text-muted mt-10">
          Demo build · powered by Qwen · grounded in CSDI Hong Kong spatial data.
        </p>
      </div>
    </main>
  );
}
