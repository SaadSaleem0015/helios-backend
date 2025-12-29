import csv
from io import StringIO

from models.lead import Lead
from typing import TypedDict
from tortoise.exceptions import IntegrityError
from models.file import File
import pandas as pd
from helpers.state import stateandtimezone


class ImportResults(TypedDict):
    successes: int
    errors: int
    duplicates: int
    invalid_phone_numbers: int


# Normalization helper
def normalize(col: str) -> str:
    return "".join(col.lower().replace(" ", "").replace("_", ""))


async def import_leads_csv(content: str, file: File) -> ImportResults:
    results = {
        "successes": 0,
        "errors": 0,
        "duplicates": 0,
        "total": 0,
        "error_reasons": set(),
    }

    state = stateandtimezone()
    time_zones = {entry["name"]: entry["zone"] for entry in state}

    try:
        df = pd.read_csv(StringIO(content)).fillna("")

        # ----------------------------------------
        # DEFINE REQUIRED + OPTIONAL COLUMNS
        # ----------------------------------------
        required_columns = {
            "firstname": "First Name",
            "lastname": "Last Name",
            "phonenumber": "Phone Number",
        }

        optional_columns = {
            "email": "Email",
            "state": "State",
            "otherdata": "Other Data",
        }

        # Normalize CSV headers
        df.columns = [col.strip() for col in df.columns]
        normalized_map = {normalize(col): col for col in df.columns}

        # ----------------------------------------
        # Check required columns exist
        # ----------------------------------------
        missing = [
            original for norm, original in required_columns.items()
            if norm not in normalized_map
        ]

        if missing:
            results["error_reasons"].add(
                "Missing required columns: " + ", ".join(missing)
            )
            results["errors"] += 1
            return results

        # ----------------------------------------
        # Rename dataframe to proper keys
        # ----------------------------------------
        column_rename_map = {}

        # required
        for norm, proper in required_columns.items():
            column_rename_map[normalized_map[norm]] = proper

        # optional
        for norm, proper in optional_columns.items():
            if norm in normalized_map:
                column_rename_map[normalized_map[norm]] = proper

        df.rename(columns=column_rename_map, inplace=True)

        # Clean values
        df = df.map(
            lambda x: x.strip() if isinstance(x, str) else str(x) if pd.notna(x) else ""
        )

        results["total"] = len(df)

        # ----------------------------------------
        # PROCESS ROWS
        # ----------------------------------------
        for idx, row in df.iterrows():
            try:
                if not row["First Name"]:
                    raise ValueError("Missing First Name.")
                if not row["Last Name"]:
                    raise ValueError("Missing Last Name.")
                if not row["Phone Number"]:
                    raise ValueError("Missing Phone Number.")

                # State → timezone
                timezone = None
                if "State" in row and row["State"]:
                    state_val = row["State"].strip().lower()
                    matching_state = next(
                        (state_name for state_name in time_zones if state_val in state_name.lower()),
                        None,
                    )
                    timezone = time_zones.get(matching_state)

                await Lead(
                    first_name=row["First Name"],
                    last_name=row["Last Name"],
                    email=row.get("Email", ""),
                    mobile=row["Phone Number"],
                    state=row.get("State", ""),
                    timezone=timezone,
                    other_data={"Other Data": row.get("Other Data", "")},
                    file=file,
                ).save()

                results["successes"] += 1

            except ValueError as ve:
                results["errors"] += 1
                results["error_reasons"].add(str(ve))

            except IntegrityError as e:
                print(e)
                results["duplicates"] += 1
                results["errors"] += 1
                results["error_reasons"].add("Duplicate entries detected.")

            except Exception as e:
                results["errors"] += 1
                results["error_reasons"].add(f"Unexpected error in row {idx + 1}: {e}")

    except Exception as e:
        results["errors"] += 1
        results["error_reasons"].add(f"Error reading the file: {e}")

    return results


def humanize_results(results: ImportResults) -> str:
    messages = []

    if results["successes"] == 0:
        messages.append(
            f"Unable to add {results['total']} row{'s' if results['total'] != 1 else ''}."
        )
        if results["error_reasons"]:
            messages.append("Reasons for failure:")
            messages.extend(f"- {reason}" for reason in results["error_reasons"])
        else:
            messages.append("There is no record found.")
        return " ".join(messages)

    messages.append(
        f"{results['successes']} row{'s' if results['successes'] != 1 else ''} successfully added."
    )

    if results["errors"] > 0:
        messages.append(
            f"Unable to add {results['errors']} row{'s' if results['errors'] != 1 else ''}."
        )
    if results["duplicates"] > 0:
        messages.append(
            f"Out of which {results['duplicates']} had invalid or duplicate values."
        )

    return " ".join(messages)
