# Sample datasets

Three synthetic CSV files for trying DataLens. They contain no real or personal data.
Each one has deliberate quality problems, so every feature has something to show.

| File | Rows | Columns | Shows |
| --- | --- | --- | --- |
| `manufacturing_data.csv` | 1,522 | 8 | Sensor readings, a PASS/FAIL result, and time-based trends. Pressure rises with temperature, so the correlation view finds a strong pair. |
| `employee_data.csv` | 402 | 7 | Categorical and numeric columns, lowercase and abbreviated spellings, impossible ages, duplicate rows. |
| `sales_data.csv` | 2,020 | 10 | Revenue is quantity times unit price, so related columns correlate. Dates, regions, and categories. |

The row counts include the duplicate rows the generator adds on purpose.

## What is in each file

**manufacturing_data.csv:** about 3% blank temperatures, 2% blank pressures, lowercase and padded
`result` values (`pass`, ` FAIL`), and about 1.5% duplicate rows. `error_code` is blank for passing
units, which makes it a useful categorical column.

**employee_data.csv:** about 5% blank salaries, 2% blank hire dates, 2% padded locations, and 3%
lowercase departments. A few `active` values use `Y`/`N` instead of `Yes`/`No`. Two ages (212 and 7)
are impossible values. There are a few duplicate rows.

**sales_data.csv:** about 2% blank revenues, 1% blank unit prices, 1.5% blank regions, and about 1%
duplicate rows. Revenue is consistent with quantity times unit price, except where it is blank.

## Regenerate

The generator is deterministic. The same seed and row counts always produce the same bytes. It needs
only pandas and numpy, which the backend already installs.

```powershell
# from the repository root, with the backend virtualenv active
python sample_data\generate_sample_data.py
```

```bash
python sample_data/generate_sample_data.py
```

Options:

- `--output-dir PATH`: where to write the files (default: this folder)
- `--seed N`: random seed (default: 42)
- `--manufacturing-rows N`, `--employee-rows N`, `--sales-rows N`: sizes before duplicates are added

For a larger demo, for example to see the 50 MB limit or slower charts, increase the row counts and
write to a folder outside the repository:

```bash
python sample_data/generate_sample_data.py --manufacturing-rows 200000 --output-dir ../demo-data
```

Large generated files shouldn't be committed. Keep them outside the repository.
