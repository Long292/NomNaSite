import cv2
import hashlib
import numpy as np
import streamlit as st

from PIL import Image
from streamlit_drawable_canvas import st_canvas
from streamlit_javascript import st_javascript

from handler.asset import download_assets, load_models, file_uploader
from handler.bbox import generate_initial_drawing, transform_fabric_box, order_boxes4nom, get_patch
from handler.translator import hcmus_translate, hvdic_render
from css import custom_style


def img2str(cv2_image):
    img_bytes = cv2.imencode('.jpg', cv2_image)[1].tobytes()
    hash_object = hashlib.sha256(img_bytes)
    hash_str = hash_object.hexdigest()
    print(hash_str)
    return hash_str
    

st.set_page_config('Digitalize old Vietnamese handwritten script for historical document archiving', '🇻🇳', 'wide')
st.markdown(custom_style, unsafe_allow_html=True)

download_assets()    
det_model, rec_model = load_models()
col1, col2 = st.columns(2)
image_name = 'test.jpg'


with st.sidebar:
    file_uploader(image_name)
    

with col1:
    raw_image = cv2.cvtColor(cv2.imread(image_name), cv2.COLOR_BGR2RGB)
    canvas_width = st_javascript('await fetch(window.location.href).then(response => window.innerWidth)')
    # canvas_width = min(canvas_width, raw_image.shape[1])
    canvas_height = raw_image.shape[0] * canvas_width / raw_image.shape[1] # For responsive canvas
    size_ratio = canvas_height / raw_image.shape[0]
    
    with st.spinner('Detecting bounding boxes containing text...'):
        boxes = det_model.predict_one_page(raw_image)
        key = img2str(raw_image)
        
        col11, col12 = st.columns(2)
        with col11:
            mode = st.radio('Mode', ('Drawing', 'Editing'), horizontal=True, label_visibility='collapsed', key=f'mode_{key}')
            st.button('**(\*)** Double-click to remove.', disabled=True)
            rec_clicked = st.button('Extract Text', type='primary', use_container_width=True)
        with col12:
            saved_format = st.radio('Type', ('csv', 'json'), horizontal=True, label_visibility='collapsed')
            st.download_button(
                label = f'📥 Export to data.{saved_format}',
                data = open(f'data/data.{saved_format}', 'r'),
                file_name = saved_format,
                use_container_width = True
            )
            st.download_button(
                label = f'🖼️ Download patches',
                data = open(f'data/data.{saved_format}', 'r'),
                file_name = saved_format,
                use_container_width = True
            )

        canvas_result = st_canvas(
            background_image = Image.open(image_name) if image_name else None,
            fill_color = 'rgba(76, 175, 80, 0.3)',
            width = max(canvas_width, 1),
            height = max(canvas_height, 1),
            stroke_width = 2,
            stroke_color = 'red',
            drawing_mode = 'rect' if mode == 'Drawing' else 'transform',
            initial_drawing = generate_initial_drawing(boxes, size_ratio),
            update_streamlit = rec_clicked,
            key = f'canvas_{key}'
        )
        
        
with col2:
    canvas_boxes = []
    if canvas_result.json_data and 'objects' in canvas_result.json_data:
        canvas_boxes = order_boxes4nom([
            transform_fabric_box(obj, size_ratio) 
            for obj in canvas_result.json_data['objects']
        ])

    with st.spinner('Recognizing text in each bounding box...'):
        with open(f'data/data.json', 'w', encoding='utf-8') as json_file:
            save_json = {
                'num_det': len(canvas_boxes), 
                'height': raw_image.shape[0], 
                'width': raw_image.shape[1], 
                'patches': []
            }
            with open(f'data/data.csv', 'w', encoding='utf-8') as txt_file:
                for idx, box in enumerate(canvas_boxes):
                    patch = get_patch(raw_image, box)
                    nom_text = rec_model.predict_one_patch(patch).strip()
                    modern_text = hcmus_translate(nom_text).strip()
                    
                    with st.expander(f':red[**Text {idx + 1:02d}**:] {nom_text}'):
                        col21, col22 = st.columns([1, 7])
                        with col21:
                            st.image(patch)
                        with col22:
                            points = sum(box.tolist(), [])
                            points = ','.join([str(round(p)) for p in points])
                            st.json({
                                'nom': nom_text, 'modern': modern_text, 'points': points, 
                                'height': patch.shape[0], 'width': patch.shape[1]
                            })
                            
                    st.markdown(f'''
                        [hcmus](https://www.clc.hcmus.edu.vn/?page_id=3039): {modern_text}<br/>
                        [hvdic](https://hvdic.thivien.net/transcript.php#trans): {hvdic_render(nom_text)}
                    ''', unsafe_allow_html=True)