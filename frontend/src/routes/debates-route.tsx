import { ArchivePage } from "../modules/debates-archive/archive-page";
import type { DebatesBootstrapData } from "../lib/types/bootstrap";

type DebatesRouteProps = {
  data: DebatesBootstrapData;
};

export function DebatesRoute({ data }: DebatesRouteProps) {
  return <ArchivePage debates={data.debates} />;
}