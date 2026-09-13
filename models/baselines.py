import os
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

def run_classical_baselines():
    print("Loading Archive Dataset for Classical ML Baselines...")
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dataset", "archive", "Malware dataset.csv")
    
    if not os.path.exists(csv_path):
        print(f"Dataset not found at {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    
    # Map classification to binary target
    df['label'] = df['classification'].apply(lambda x: 1 if x.strip().lower() == 'malware' else 0)
    
    print("Extracting tabular features...")
    # Group by process hash to extract statistical summaries per process
    grouped = df.groupby('hash')
    
    X = []
    y = []
    
    for _, group in grouped:
        # Extract features (mean and std of critical columns)
        features = [
            group['usage_counter'].mean(),
            group['usage_counter'].std(),
            group['maj_flt'].mean(),
            group['min_flt'].mean(),
            group['nvcsw'].mean(),
            group['nivcsw'].mean(),
        ]
        # Replace NaNs with 0 (if any std is NaN due to single row)
        features = [0 if np.isnan(f) else f for f in features]
        X.append(features)
        y.append(group['label'].iloc[0])
        
    X = np.array(X)
    y = np.array(y)
    
    print(f"Extracted {len(X)} process summaries. Training Random Forest...")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    
    preds = rf.predict(X_test)
    
    acc = accuracy_score(y_test, preds)
    print(f"\nRandom Forest Baseline Accuracy: {acc * 100:.2f}%\n")
    print("Classification Report:")
    print(classification_report(y_test, preds))
    print("If the Tri-Modal Deep Learning network achieves > 72% (from our earlier run) or higher, it proves the spatial/temporal extraction provides value beyond simple tabular statistics.")

if __name__ == "__main__":
    run_classical_baselines()
