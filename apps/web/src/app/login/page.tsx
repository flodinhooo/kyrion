import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { BrandAsset } from "@/components/brand-asset";
import { currentUser, isSetupRequired } from "@/lib/server-auth";

export default async function LoginPage() {
  if (await currentUser()) redirect("/");
  const setupRequired = await isSetupRequired();
  return (
    <main className="auth-stage">
      <section className="auth-card">
        <BrandAsset variant="mark" priority />
        <p className="eyebrow">{setupRequired ? "Einmalige Einrichtung" : "Willkommen zurück"}</p>
        <h1>{setupRequired ? "Dein lokales Kyrion" : "Bei Kyrion anmelden"}</h1>
        <p>{setupRequired === null ? "Kyrion Core ist momentan nicht erreichbar." : setupRequired
          ? "Erstelle den lokalen Owner. Es gibt keine öffentliche Registrierung."
          : "Deine privaten Bereiche und Gespräche sind geschützt."}</p>
        {setupRequired !== null && <AuthForm setup={setupRequired} />}
      </section>
    </main>
  );
}
