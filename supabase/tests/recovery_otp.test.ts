import { hasRecentEmailConfirmation } from "../functions/_shared/v2.ts";
Deno.test("recovery requires recent OTP, not password alone", () => {
  const now = Math.floor(Date.now()/1000);
  for (const amr of [[], [{method:"password",timestamp:now}], [{method:"otp",timestamp:now-601}], [{method:"otp",timestamp:now+120}]]) {
    if (hasRecentEmailConfirmation({amr},600)) throw new Error("Unverified recovery accepted");
  }
  if (!hasRecentEmailConfirmation({amr:[{method:"otp",timestamp:now}]},600)) throw new Error("Fresh OTP rejected");
});
