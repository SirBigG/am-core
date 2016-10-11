import React from 'react';

import ImageUploadField from './fields/ImageUploadField'
import FieldErrorsMixin from '../mixins/FieldErrorsMixin';

const PhotoSet = React.createClass({
    mixins: [FieldErrorsMixin],
    getInitialState(){
        return { image1: '', image2: '', image3: '', image4: ''}
    },
    // TODO: need to normal realization
    handleImageChange(name, event) {
        event.preventDefault();
        let reader = new FileReader();
        let file = event.target.files[0];

        reader.onload = () => {
            this.state[name] = reader.result;
            this.setState(this.state)
        };
        reader.readAsDataURL(file)
    },
    render() {
        var errors = this.renderErrors(this.props.errors);
        // TODO: replace with array adding class and array lenghs props
        var ints = [1, 2, 3, 4];
        var fieldNodes = ints.map((number) => {
            return <div className="col-md-3" key={number}>
                <ImageUploadField image_url={this.state['image' + number]} name={'image' + number} onChange={this.handleImageChange.bind(this, 'image' + number)}/>
            </div>
            });
        return (
            <div>
                {errors}
                <div className="row">
                    {fieldNodes}
                </div>
            </div>
        )
    }
});


export default PhotoSet;
