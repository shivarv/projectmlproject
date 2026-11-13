import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression


# ---------------- Custom logic ----------------

def fit(X, y):
    """Return (intercept, coefficients) using the Normal Equation: b = (XᵀX)⁻¹ Xᵀy"""
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)

    # add a column of 1s so the intercept is learned like any other coefficient
    X_b = np.hstack([np.ones((X.shape[0], 1)), X])

    b = np.linalg.inv(X_b.T @ X_b) @ X_b.T @ y

    intercept = b[0]
    coefficients = b[1:]
    return intercept, coefficients


def predict(X, intercept, coefficients):
    """price = intercept + b1*x1 + b2*x2 + ... for every row"""
    X = np.array(X, dtype=float)
    return intercept + X @ coefficients


# ---------------- Data ----------------

# Features: [size in sqft, age in years]
X = [[1000, 10],
     [1500, 5],
     [2000, 20],
     [2500, 2],
     [1200, 15]]

# Target: price in $1000s
y = [200, 320, 330, 500, 220]

new_house = [[1800, 8]]


# ---------------- Custom ----------------

intercept, coefficients = fit(X, y)
custom_pred = predict(new_house, intercept, coefficients)

# ---------------- Standard (sklearn) ----------------

model = LinearRegression().fit(X, y)
sk_pred = model.predict(new_house)

# ---------------- Compare ----------------

print("              Custom            sklearn")
print(f"Intercept:    {intercept:<17.4f} {model.intercept_:.4f}")
print(f"Coef size:    {coefficients[0]:<17.4f} {model.coef_[0]:.4f}")
print(f"Coef age:     {coefficients[1]:<17.4f} {model.coef_[1]:.4f}")
print(f"Prediction:   {custom_pred[0]:<17.4f} {sk_pred[0]:.4f}")


# ---------------- 3D plot method ----------------

def plot_3d(X, y, model, new_point, title):
    """Plot actual data, the best-fit plane and a new prediction using sklearn's model.predict()."""
    X_arr = np.array(X, dtype=float)
    sizes, ages = X_arr[:, 0], X_arr[:, 1]

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(sizes, ages, y, color='blue', s=50, label='Actual Data')

    # grid of (size, age) values covering the data
    x1, x2 = np.meshgrid(np.linspace(sizes.min(), sizes.max(), 20),
                         np.linspace(ages.min(), ages.max(), 20))

    # plane: let sklearn predict a price for every grid point
    z = model.predict(np.c_[x1.ravel(), x2.ravel()]).reshape(x1.shape)
    ax.plot_surface(x1, x2, z, color='red', alpha=0.4)

    # the new house, predicted by sklearn
    new_pred = model.predict([new_point])[0]
    ax.scatter(new_point[0], new_point[1], new_pred,
               color='green', s=120, marker='*', label='New house prediction')

    ax.set_xlabel('Size (sqft)')
    ax.set_ylabel('Age (years)')
    ax.set_zlabel('Price ($1000s)')
    ax.set_title(title)
    ax.legend()

    plt.show()


# ---------------- Plot using the standard (sklearn) outcome ----------------

plot_3d(X, y, model, new_house[0],
        'Multiple Linear Regression Best Fit Plane (3D) - sklearn')
