import { redirect } from "next/navigation";
import { LoginScreen } from "@/components/login-screen";
import { currentUser, isSetupRequired } from "@/lib/server-auth";

export default async function SignupPage() {
  if (await currentUser()) redirect("/");
  return <LoginScreen setupRequired={await isSetupRequired()} registration />;
}
