import React from 'react';

import ImageUploadField from './ImageUploadField'

const PhotoSet = React.createClass({
    render() {
        // TODO: replace with array adding class and array lenghs props
        var ints = [1, 2, 3, 4];
        var fieldNodes = ints.map((number) => {
            return <div className="col-md-3" key={number}>
                <ImageUploadField name={'photo' + number} />
            </div>
            });
        return (
            <div>
                {fieldNodes}
            </div>
        )
    }
});


export default PhotoSet;
