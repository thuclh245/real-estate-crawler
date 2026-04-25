# 11 - Optional ML Baseline Specification

## Purpose

ML is optional. It demonstrates that clean Gold data can support downstream valuation tasks. It must not become the main focus.

## Dataset source

Use `gold_listing_current` or a feature table generated from Gold.

## Clean filter

Only use records satisfying:

```sql
price_value_vnd IS NOT NULL
AND area_m2 IS NOT NULL
AND unit_price_vnd_m2 IS NOT NULL
AND district IS NOT NULL
AND property_type IS NOT NULL
AND is_valid_for_ml = true
```

## Target

```text
unit_price_vnd_m2
```

Reason: total price is too dependent on area.

## Features

```text
district
ward_old or ward_new
property_type
area_m2
bedrooms
bathrooms
floors
frontage_m
entrance_width_m
legal_status
furniture_status
image_count
seller_type
```

## Models

Minimum:

```text
Linear Regression
Random Forest Regressor
```

Optional:

```text
XGBoost
CatBoost
```

## Metrics

```text
MAE
RMSE
R2
MAPE optional
```

## Outputs

```text
model performance table
predicted vs actual chart
feature importance
error analysis by district/property_type
limitations
```

## Acceptance tests

```text
[ ] ML dataset is generated from Gold only.
[ ] Train/test split exists.
[ ] At least one baseline model trains.
[ ] MAE/RMSE/R2 are reported.
[ ] Feature importance or coefficients are shown.
[ ] Limitations are written clearly.
```
