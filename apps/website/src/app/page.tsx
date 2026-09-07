import de from "@/locales/de.json";
import en from "@/locales/en.json";

export default function HomePage() {
  return (
    <main>
      <h1>{en.title}</h1>
      <p>{en.comingSoon}</p>
      <p lang="de">{de.comingSoon}</p>
    </main>
  );
}
