import type { EditorialBootstrapData } from "../lib/types/bootstrap";
import { EditorialPage } from "../modules/editorial/editorial-page";

type EditorialRouteProps = {
  data: EditorialBootstrapData;
};

export function EditorialRoute({ data }: EditorialRouteProps) {
  return <EditorialPage models={data.models} />;
}
