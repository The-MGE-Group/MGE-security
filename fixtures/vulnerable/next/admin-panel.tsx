"use client";
// Deliberately vulnerable. Test fixture only.
import { createClient } from "@supabase/supabase-js";

// Planted problem: the service-role key in code that runs in the browser.
export const admin = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!);
