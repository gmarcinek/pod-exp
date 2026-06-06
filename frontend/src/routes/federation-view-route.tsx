import type { FederationViewBootstrapData } from "../lib/types/bootstrap";
import { FederationViewPage } from "../modules/federation/federation-view-page";

type FederationViewRouteProps = {
  data: FederationViewBootstrapData;
};

export function FederationViewRoute({ data }: FederationViewRouteProps) {
  return <FederationViewPage record={data.record} />;
}
