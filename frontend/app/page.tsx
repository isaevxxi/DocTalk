export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-4">DokTalk</h1>
        <p className="text-xl text-muted-foreground mb-8">
          Ambient Clinical Scribe for Russian Healthcare
        </p>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div className="border rounded-lg p-4">
            <h2 className="font-semibold mb-2">SOAP Notes</h2>
            <p className="text-sm text-muted-foreground">
              Automated clinical documentation from encounter audio
            </p>
          </div>
          <div className="border rounded-lg p-4">
            <h2 className="font-semibold mb-2">ICD-10 Suggestions</h2>
            <p className="text-sm text-muted-foreground">
              AI-powered diagnostic code recommendations
            </p>
          </div>
          <div className="border rounded-lg p-4">
            <h2 className="font-semibold mb-2">Compliance Ready</h2>
            <p className="text-sm text-muted-foreground">
              152-FZ, 323-FZ, and Order 965n compliant
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
