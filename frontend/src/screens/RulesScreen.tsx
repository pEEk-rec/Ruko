// "My rules": the optional profile fields the backend accepts (UserProfile).
// Saved on the device only, and sent with each analyze request.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody } from "../components/Layout";
import { PlansList } from "../components/PlansList";
import { ProfileFields } from "../components/ProfileFields";
import { RukoMessage } from "../components/RukoMessage";
import { loadProfile, saveProfile } from "../services/device";
import type { UserProfile } from "../types/api";

export function RulesScreen({ onBack }: { onBack: () => void }) {
  const t = useCopy();
  const [profile, setProfile] = useState<UserProfile>(() => loadProfile());
  const [status, setStatus] = useState<string | null>(null);

  /** Removing a plan takes effect at once (it is saved straight away, not with "Save"). */
  function removePlan(id: string) {
    const next = { ...profile, plans: (profile.plans ?? []).filter((plan) => plan.id !== id) };
    setProfile(next);
    saveProfile({ ...loadProfile(), plans: next.plans });
  }

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton
            label={t.save}
            onClick={() => setStatus(saveProfile(profile) ? t.saved : t.saveFailed)}
          />
          <ActionButton label={t.back} onClick={onBack} variant="text" />
          {status ? (
            <p className="screen-footer" role="status">
              {status}
            </p>
          ) : null}
        </>
      }
    >
      <Eyebrow>{t.rulesEyebrow}</Eyebrow>
      <RukoMessage text={t.rulesTitle} subtext={t.rulesBody} />
      <ProfileFields
        profile={profile}
        onChange={(next) => {
          setProfile(next);
          setStatus(null);
        }}
      />
      <PlansList plans={profile.plans ?? []} onRemove={removePlan} />
    </ScreenBody>
  );
}
