import { DebateViewPage } from "../modules/debate-view/debate-view-page";
import type { DebateViewBootstrapData } from "../lib/types/bootstrap";

type DebateViewRouteProps = {
  data: DebateViewBootstrapData;
};

export function DebateViewRoute({ data }: DebateViewRouteProps) {
  return <DebateViewPage debate={data.debate} />;
}