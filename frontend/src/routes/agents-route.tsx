import { AgentsPage } from "../modules/agents/agents-page";
import type { AgentsBootstrapData } from "../lib/types/bootstrap";

type AgentsRouteProps = {
  data: AgentsBootstrapData;
};

export function AgentsRoute({ data }: AgentsRouteProps) {
  return <AgentsPage agents={data.agents} />;
}
