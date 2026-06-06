import { FederationPage } from "../modules/federation/federation-page";
import type { FederationBootstrapData } from "../lib/types/bootstrap";

type FederationRouteProps = {
  data: FederationBootstrapData;
};

export function FederationRoute({ data }: FederationRouteProps) {
  return <FederationPage agents={data.agents} models={data.models} />;
}
