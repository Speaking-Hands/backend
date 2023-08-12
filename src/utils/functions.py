import pandas as pd
import numpy as np

def create_frame_row(frame_num, results):
    """
    frame, x_face_0, x_face_1, x_face_2...y_face_1, y_face_2...x_right_hand_1...x_left_hand_1...x_pose_1
    """
    # Frame row object for parquet
    frame_row = pd.DataFrame()

    # Frame number
    frame_row["frame"] = [frame_num]

    # Frame zones
    frame_zones = {
        "face": {
            "size": 468,
            "results": results.face_landmarks
        },
        "right_hand": {
            "size": 21,
            "results": results.right_hand_landmarks
        },
        "left_hand": {
            "size": 21,
            "results": results.left_hand_landmarks
        },
        "pose": {
            "size": 33,
            "results": results.pose_landmarks
        }
    }

    for zone in frame_zones.keys():

        if frame_zones[zone]["results"]:
            # Guardamos valores de x, y, z
            x_values = [data_point.x for data_point in frame_zones[zone]["results"].landmark]
            y_values = [data_point.y for data_point in frame_zones[zone]["results"].landmark]
            z_values = [data_point.z for data_point in frame_zones[zone]["results"].landmark]
            # Crear un diccionario con todas las columnas y sus respectivos valores
            data = {
                **{f'x_{zone}_{i}': x_values[i] for i in range(frame_zones[zone]["size"])},
                **{f'y_{zone}_{i}': y_values[i] for i in range(frame_zones[zone]["size"])},
                **{f'z_{zone}_{i}': z_values[i] for i in range(frame_zones[zone]["size"])},
            }
            # Agregar las columnas
            frame_row = pd.concat([frame_row, pd.DataFrame(data, index=[0])], axis=1)
        
        else:
            # Crear un diccionario con todas las columnas y sus valores nulos
            data = {
                **{f'x_{zone}_{i}': np.nan for i in range(frame_zones[zone]["size"])},
                **{f'y_{zone}_{i}': np.nan for i in range(frame_zones[zone]["size"])},
                **{f'z_{zone}_{i}': np.nan for i in range(frame_zones[zone]["size"])},
            }
            # Agregar las columnas
            frame_row = pd.concat([frame_row, pd.DataFrame(data, index=[0])], axis=1)

    return frame_row