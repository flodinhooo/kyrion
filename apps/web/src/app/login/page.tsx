import { redirect } from "next/navigation";
import { LoginScreen } from "@/components/login-screen";
import { currentUser, isSetupRequired } from "@/lib/server-auth";

export default async function LoginPage() {
  if (await currentUser()) redirect("/");
  const setupRequired = await isSetupRequired();
  return <LoginScreen setupRequired={setupRequired} />;
}
