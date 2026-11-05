// Deliberately vulnerable. Test fixture only (a Next.js route handler: server code).
import { supabase } from "../../../session";

export async function GET() {
  // Planted problem: trusting getSession() on the server.
  const { data } = await supabase.auth.getSession();
  return Response.json({ id: data.session?.user.id });
}
