import { EditorialsPage } from "../modules/editorials/editorials-page";
import type { EditorialsBootstrapData } from "../lib/types/bootstrap";

type EditorialsRouteProps = {
  data: EditorialsBootstrapData;
};

export function EditorialsRoute({ data }: EditorialsRouteProps) {
  return <EditorialsPage editorials={data.editorials} />;
}
