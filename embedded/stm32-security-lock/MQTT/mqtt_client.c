/* Agent 4 */
#include "mqtt_client.h"
#include <string.h>
Decision_t Parse_Decision(const char *p) {
  if (strstr(p, "\"granted\"")) return DECISION_GRANTED;
  if (strstr(p, "\"denied\""))  return DECISION_DENIED;
  return DECISION_UNKNOWN;   /* không rõ thì coi như không mở khóa */
}
