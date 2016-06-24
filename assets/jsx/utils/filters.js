
module.exports = {
    truncate: (str, num) => {
        var words = str.split(' ');
        words = words.splice(0, num);
        return words.join(' ');
    },

    orderBy: (arr, len) => {
        var chunks = [],
            i = 0,
            n = arr.length;
        while (i < n) {
            chunks.push(arr.slice(i, i += len));
        }
        return chunks;
    }
};